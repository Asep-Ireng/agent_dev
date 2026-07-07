"""
dev_tools.py — Physical operation tools for the autonomous developer agent.

Safety features added in this revision:
  - Command blocklist (TerminalExecutionTool): rejects catastrophic shell patterns before exec.
  - Per-file threading.Lock registry: serialises concurrent writes to the same path.
  - Syntax / size validation (WriteFileTool, ReplaceInFileTool, EditFileLinesTool,
    InsertAtLineTool): content is checked before hitting disk.
  - BatchReplaceFileContentTool: transactional multi-chunk replacement with anchor
    validation and bottom-to-top application to eliminate line-drift corruption.
"""

import os
import re
import subprocess
import threading
from collections import defaultdict
from typing import Any
from pydantic import BaseModel, Field

from syntax_guard import (
    validate_content,
    validate_file_size,
    increment_failure,
)


# ==================================
# MODULE-LEVEL SAFETY STATE
# ==================================

# Per-file write locks — process-scoped (single-worker assumption).
_file_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


def _get_file_lock(abs_path: str) -> threading.Lock:
    """Return (or lazily create) the lock for a given absolute file path."""
    return _file_locks[abs_path]


# ==================================
# COMMAND BLOCKLIST
# ==================================

# Patterns are matched against the *lowercased* command string.
# Each entry is a compiled regex. Matched commands are rejected before execution.
_BLOCKED_COMMAND_PATTERNS: list[re.Pattern] = [
    re.compile(p)
    for p in [
        r"rm\s+-rf\s+/",          # rm -rf / (and variants)
        r"rm\s+-rf\s+[\"']?/",
        r"del\s+/s\s+/q\s+[a-z]:\\",  # del /s /q C:\  (Windows nuke)
        r"format\s+[a-z]:",        # format C:
        r"mkfs",                   # Linux filesystem format
        r"shutdown",               # system shutdown / reboot
        r"reboot",
        r"halt",
        r"curl.+\|\s*(ba)?sh",    # curl | sh  (pipe-to-shell attack)
        r"wget.+\|\s*(ba)?sh",
        r"powershell\s+-e(nc(odedcommand)?)?",  # base64-encoded PS
        r"iex\s*\(",               # Invoke-Expression
    ]
]


def _is_blocked_command(command: str) -> tuple[bool, str]:
    """Return (True, pattern_description) if the command matches a blocklist entry."""
    lower = command.lower()
    for pattern in _BLOCKED_COMMAND_PATTERNS:
        if pattern.search(lower):
            return True, pattern.pattern
    return False, ""


# ==================================
# SHARED VALIDATION HELPER
# ==================================


def _validate_and_guard(file_path: str, content: str) -> str | None:
    """Run size + syntax validation and failure-budget accounting.

    Returns None if content is safe to write.
    Returns a [SYSTEM …] error string if the write must be blocked.
    """
    # Size check first (cheap)
    ok, err = validate_file_size(content)
    if not ok:
        exhausted = increment_failure()
        if exhausted:
            return (
                "[SYSTEM CRITICAL] Failure budget exhausted (3 validation errors in this run). "
                "File writes are now halted. Report the task as failed and stop."
            )
        return f"[SYSTEM BLOCKED] {err}. Fix the content and try again."

    # Syntax check
    ok, err = validate_content(file_path, content)
    if not ok:
        exhausted = increment_failure()
        if exhausted:
            return (
                "[SYSTEM CRITICAL] Failure budget exhausted (3 syntax errors in this run). "
                "File writes are now halted. Report the task as failed and stop."
            )
        return f"[SYSTEM BLOCKED] Syntax validation failed for {file_path}: {err}. Fix the error and try again."

    return None  # all good


# ==================================
# SCHEMAS
# ==================================


class TerminalExecutionSchema(BaseModel):
    command: str = Field(
        description="The shell command to execute, e.g. 'npm install next' or 'mkdir src'."
    )


class WriteFileSchema(BaseModel):
    file_path: str = Field(
        description="The relative path to the file to create or overwrite, e.g. 'src/App.tsx'"
    )
    content: str = Field(
        description="The complete code/text content to write to the file."
    )


class ReadFileSchema(BaseModel):
    file_path: str = Field(
        description="The relative path to the file to read, e.g. 'src/App.tsx'"
    )
    start_line: int = Field(
        default=0,
        description="Optional starting line number (0-based). Use 0 to start from the beginning.",
    )
    end_line: int = Field(
        default=-1,
        description="Optional ending line number (0-based, inclusive). Use -1 to read to the end.",
    )


class ReplaceInFileSchema(BaseModel):
    file_path: str = Field(
        description="The relative path to the file to edit, e.g. 'src/App.tsx'"
    )
    old_text: str = Field(
        description="The exact text to find and replace. Must match the file content EXACTLY, including whitespace and indentation."
    )
    new_text: str = Field(description="The new text to replace the old text with.")


class EditFileLinesSchema(BaseModel):
    file_path: str = Field(
        description="The relative path to the file to edit, e.g. 'src/App.tsx'"
    )
    start_line: int = Field(
        description="The starting line number (1-based, inclusive) of the range to replace."
    )
    end_line: int = Field(
        description="The ending line number (1-based, inclusive) of the range to replace."
    )
    new_content: str = Field(
        description="The new content to replace the specified line range with."
    )


class InsertAtLineSchema(BaseModel):
    file_path: str = Field(
        description="The relative path to the file to edit, e.g. 'src/App.tsx'"
    )
    line_number: int = Field(
        description="The line number (1-based) where the new content will be inserted. The new content will appear BEFORE this line."
    )
    content: str = Field(
        description="The content to insert at the specified line number."
    )


class ReplaceChunk(BaseModel):
    target_content: str = Field(
        description=(
            "The exact text to anchor on and replace. Must appear EXACTLY ONCE in the file. "
            "If the anchor is not found or appears more than once, the entire transaction is rolled back."
        )
    )
    replacement_content: str = Field(
        description="The new text to substitute in place of target_content."
    )


class BatchReplaceFileContentSchema(BaseModel):
    file_path: str = Field(
        description="The relative path to the file to edit, e.g. 'src/App.tsx'"
    )
    chunks: list[ReplaceChunk] = Field(
        description=(
            "Ordered list of {target_content, replacement_content} pairs. "
            "Applied bottom-to-top (by position) to prevent offset drift. "
            "ALL anchors must match exactly once — a single mismatch rolls back the whole transaction."
        )
    )


class ReportTaskStatusSchema(BaseModel):
    status: str = Field(
        description="The overall status: 'success', 'failed', or 'partial'. Use 'partial' if some things worked but not everything."
    )
    summary: str = Field(
        description="A brief summary of what was accomplished (or what failed). Be specific about files and changes."
    )


# ==================================
# TOOLS
# ==================================


class TerminalExecutionTool:
    name: str = "execute_terminal_command"
    description: str = (
        "Executes a shell command in the specified workspace directory and returns the stdout and stderr.\n"
        "ENVIRONMENT: You are on Windows (cmd/PowerShell) - use Windows commands. NEVER run recursive directory listings like 'dir /s'. Use 'dir' (without /s).\n"
        "When scaffolding projects, ALWAYS use non-interactive flags (e.g. 'npx -y ...', 'npm init -y'). NEVER run interactive prompts.\n"
        "PRE-COMPLETION VERIFICATION: Test-run the application before finishing to verify it works (e.g. 'npm run dev' with a timeout), fix any errors, and kill the dev server.\n"
        "SAFETY: Certain destructive or system-level commands are blocked and will be rejected immediately."
    )
    args_schema = TerminalExecutionSchema

    def __init__(
        self,
        workspace_path: str,
        require_approval: bool = False,
        approval_callback: Any = None,
        stream_callback: Any = None,
    ):
        self.workspace_path = workspace_path
        self.require_approval = require_approval
        self.approval_callback = approval_callback
        self.stream_callback = stream_callback

        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path, exist_ok=True)

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, command: str) -> str:
        """Execute the command using Popen with real-time streaming."""

        # ---- Blocklist check (before approval / execution) ----
        blocked, pattern = _is_blocked_command(command)
        if blocked:
            return (
                f"[SYSTEM BLOCKED] Command rejected by safety blocklist (matched pattern: '{pattern}'). "
                f"This command is considered destructive or unsafe and will NOT be executed. "
                f"Rethink your approach without using this command."
            )

        if self.require_approval and self.approval_callback:
            try:
                approved, feedback = self.approval_callback(command)
                if not approved:
                    reason = (
                        feedback.strip() if feedback else "No specific reason provided."
                    )
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user (your manager) explicitly REJECTED this command.\nThey said: '{reason}'.\nDo NOT run this command again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."

        try:
            cwd = os.path.abspath(self.workspace_path)

            if self.stream_callback:
                self.stream_callback("cmd_start", {"cwd": cwd, "cmd": command})

            proc = subprocess.Popen(
                command,
                shell=True,
                cwd=self.workspace_path,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                bufsize=1,
            )

            stdout_lines = []
            stderr_lines = []

            def read_stream(pipe, collector, stream_type):
                try:
                    for line in iter(pipe.readline, ""):
                        if line:
                            collector.append(line)
                            if self.stream_callback:
                                self.stream_callback(stream_type, line.rstrip("\n\r"))
                except (ValueError, OSError):
                    pass
                finally:
                    pipe.close()

            stdout_thread = threading.Thread(
                target=read_stream, args=(proc.stdout, stdout_lines, "stdout")
            )
            stderr_thread = threading.Thread(
                target=read_stream, args=(proc.stderr, stderr_lines, "stderr")
            )
            stdout_thread.start()
            stderr_thread.start()

            import time
            import platform

            def kill_process_tree(pid: int):
                if platform.system() == "Windows":
                    try:
                        subprocess.run(
                            f"taskkill /F /T /PID {pid}",
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception:
                        pass
                else:
                    try:
                        import os
                        import signal
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass

            from run_manager import _get_run
            active_run = _get_run(None)
            abort_event = active_run["abort"] if active_run else None

            start_time = time.time()
            timeout = 300.0
            aborted = False
            timed_out = False

            while True:
                if proc.poll() is not None:
                    break

                if abort_event and abort_event.is_set():
                    aborted = True
                    kill_process_tree(proc.pid)
                    proc.wait()
                    break

                if time.time() - start_time > timeout:
                    timed_out = True
                    kill_process_tree(proc.pid)
                    proc.wait()
                    break

                time.sleep(0.1)

            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            if aborted:
                if self.stream_callback:
                    self.stream_callback(
                        "stderr", "[ABORTED] Command execution aborted by user."
                    )
                return "Command execution aborted by user."

            if timed_out:
                if self.stream_callback:
                    self.stream_callback(
                        "stderr", "[TIMEOUT] Command killed after 300 seconds."
                    )
                return "Command execution timed out after 300 seconds."

            returncode = proc.returncode
            stdout_text = "".join(stdout_lines)
            stderr_text = "".join(stderr_lines)

            if self.stream_callback:
                self.stream_callback(
                    "cmd_end", {"exit_code": returncode, "success": returncode == 0}
                )

            # Truncate output to avoid wasting tokens on massive listings.
            # stdout: keep the HEAD (first N chars) — useful for scaffolding/install logs.
            # stderr: keep the TAIL (last N chars) — errors appear at the end, not the start.
            MAX_OUTPUT = 5000
            if len(stdout_text) > MAX_OUTPUT:
                stdout_text = (
                    stdout_text[:MAX_OUTPUT]
                    + f"\n\n... [STDOUT TRUNCATED — {len(''.join(stdout_lines))} chars total, showing first {MAX_OUTPUT}. Avoid recursive listings like 'dir /s' or 'tree'.]\n"
                )
            if len(stderr_text) > MAX_OUTPUT:
                stderr_text = (
                    f"... [STDERR TRUNCATED — {len(''.join(stderr_lines))} chars total, showing last {MAX_OUTPUT}] ...\n\n"
                    + stderr_text[-MAX_OUTPUT:]
                )

            output = f"[CWD] {cwd}\n"
            output += f"[CMD] {command}\n"
            if stdout_text:
                output += f"[STDOUT]\n{stdout_text}\n"
            if stderr_text:
                output += f"[STDERR]\n{stderr_text}\n"
            output += f"[EXIT] {returncode}\n"

            if returncode == 0:
                return f"[SUCCESS] Command executed.\n{output}"
            else:
                return f"[FAILED] Exit code {returncode}.\n{output}"
        except Exception as e:
            return f"Error executing command: {str(e)}"


class WriteFileTool:
    name: str = "write_file"
    description: str = (
        "Writes content to a file in the workspace directory. Automatically creates parent directories if they don't exist.\n"
        "ALWAYS use this tool to save NEW source code. Do NOT use echo or cat to write blocks of code in the terminal.\n"
        "Content is validated for syntax (Python/JSON) and size before writing. Invalid content is rejected."
    )
    args_schema = WriteFileSchema

    def __init__(
        self,
        workspace_path: str,
        require_approval: bool = False,
        approval_callback: Any = None,
    ):
        self.workspace_path = workspace_path
        self.require_approval = require_approval
        self.approval_callback = approval_callback

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, file_path: str, content: str) -> str:
        if self.require_approval and self.approval_callback:
            try:
                display_content = content[:200] + ("..." if len(content) > 200 else "")
                approved, feedback = self.approval_callback(
                    f"WRITE_FILE: {file_path}\n\nCONTENT PREVIEW:\n{display_content}"
                )
                if not approved:
                    reason = (
                        feedback.strip() if feedback else "No specific reason provided."
                    )
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user explicitly REJECTED writing to this file.\nThey said: '{reason}'.\nDo NOT try this again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."

        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            workspace_abs = os.path.abspath(self.workspace_path) + os.sep
            if not (target_path + os.sep).startswith(workspace_abs):
                return "[SYSTEM] Access denied. You can only write files inside the workspace directory."

            # ---- Validation before touching the file ----
            guard_error = _validate_and_guard(file_path, content)
            if guard_error:
                return guard_error

            with _get_file_lock(target_path):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)

            return f"[SUCCESS] File written successfully to {file_path}"
        except Exception as e:
            return f"[FAILED] Error writing file: {str(e)}"


class ReadFileTool:
    name: str = "read_file"
    description: str = (
        "Reads the content of a file in the workspace. You can optionally specify a line range.\n"
        "When you need to EDIT an existing file, you MUST ALWAYS use Read File first to see the current content and exact line numbers."
    )
    args_schema = ReadFileSchema

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, file_path: str, start_line: int = 0, end_line: int = -1) -> str:
        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            workspace_abs = os.path.abspath(self.workspace_path) + os.sep
            if not (target_path + os.sep).startswith(workspace_abs):
                return "[SYSTEM] Access denied. You can only read files inside the workspace directory."

            if not os.path.exists(target_path):
                return f"[FAILED] File not found: {file_path}"

            with open(target_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)

            if end_line == -1:
                end_line = total_lines - 1

            start_line = max(0, min(start_line, total_lines - 1))
            end_line = max(start_line, min(end_line, total_lines - 1))

            selected = lines[start_line : end_line + 1]

            numbered = ""
            for i, line in enumerate(selected):
                numbered += f"{start_line + i + 1:4d} | {line}"

            return f"[SUCCESS] {file_path} ({total_lines} lines total, showing {start_line + 1}-{end_line + 1})\n{numbered}"
        except Exception as e:
            return f"[FAILED] Error reading file: {str(e)}"


class ReplaceInFileTool:
    name: str = "replace_in_file"
    description: str = (
        "Finds and replaces an exact text match in a file. Use this if you have a unique text snippet to match without rewriting the whole file.\n"
        "You MUST use the Read File tool first to see the exact content. If the old_text is not found exactly, the operation will fail.\n"
        "For multiple simultaneous replacements in the same file, prefer batch_replace_file_content instead."
    )
    args_schema = ReplaceInFileSchema

    def __init__(
        self,
        workspace_path: str,
        require_approval: bool = False,
        approval_callback: Any = None,
    ):
        self.workspace_path = workspace_path
        self.require_approval = require_approval
        self.approval_callback = approval_callback

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, file_path: str, old_text: str, new_text: str) -> str:
        if self.require_approval and self.approval_callback:
            try:
                old_preview = old_text[:150] + ("..." if len(old_text) > 150 else "")
                new_preview = new_text[:150] + ("..." if len(new_text) > 150 else "")
                approved, feedback = self.approval_callback(
                    f"REPLACE_IN_FILE: {file_path}\n\nOLD TEXT:\n{old_preview}\n\nNEW TEXT:\n{new_preview}"
                )
                if not approved:
                    reason = (
                        feedback.strip() if feedback else "No specific reason provided."
                    )
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user REJECTED this edit.\nThey said: '{reason}'.\nDo NOT try this again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."

        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            workspace_abs = os.path.abspath(self.workspace_path) + os.sep
            if not (target_path + os.sep).startswith(workspace_abs):
                return "[SYSTEM] Access denied. You can only edit files inside the workspace directory."

            if not os.path.exists(target_path):
                return f"[FAILED] File not found: {file_path}"

            with _get_file_lock(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    content = f.read()

                count = content.count(old_text)
                if count == 0:
                    return f"[FAILED] Could not find the exact text to replace in {file_path}. Make sure you're matching the file content exactly, including whitespace. Use Read File to check the current content."

                if count > 1:
                    return f"[FAILED] Found {count} occurrences of the text in {file_path}. Please provide a more specific/unique text snippet to match exactly one location."

                new_content = content.replace(old_text, new_text, 1)

                # ---- Validate resulting content ----
                guard_error = _validate_and_guard(file_path, new_content)
                if guard_error:
                    return guard_error

                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

            return f"[SUCCESS] Replaced text in {file_path}. {len(old_text)} chars replaced with {len(new_text)} chars."
        except Exception as e:
            return f"[FAILED] Error editing file: {str(e)}"


class EditFileLinesTool:
    name: str = "edit_file_lines"
    description: str = (
        "Replaces a specific range of lines in a file with new content. Use this for surgical edits.\n"
        "Never rewrite a whole file just to change a few lines. You MUST use Read File first to get the correct line numbers."
    )
    args_schema = EditFileLinesSchema

    def __init__(
        self,
        workspace_path: str,
        require_approval: bool = False,
        approval_callback: Any = None,
    ):
        self.workspace_path = workspace_path
        self.require_approval = require_approval
        self.approval_callback = approval_callback

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, file_path: str, start_line: int, end_line: int, new_content: str) -> str:
        if self.require_approval and self.approval_callback:
            try:
                msg = f"EDIT_FILE_LINES: {file_path}\nRANGE: {start_line}-{end_line}\n\nNEW CONTENT PREVIEW:\n{new_content[:100]}..."
                approved, feedback = self.approval_callback(msg)
                if not approved:
                    return f"[REJECTED] {feedback}"
            except InterruptedError:
                return "[SYSTEM] Aborted."

        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            workspace_abs = os.path.abspath(self.workspace_path) + os.sep
            if not (target_path + os.sep).startswith(workspace_abs):
                return "[DENIED] Outside workspace."

            if not os.path.exists(target_path):
                return "[FAILED] Not found."

            with _get_file_lock(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                idx_start = start_line - 1
                idx_end = end_line

                if idx_start < 0 or idx_start >= len(lines) or idx_end < idx_start:
                    return f"[FAILED] Invalid range {start_line}-{end_line} for file with {len(lines)} lines."

                new_lines = new_content.splitlines(keepends=True)
                if new_content and not new_content.endswith("\n"):
                    new_lines[-1] = new_lines[-1] + "\n"

                result_lines = lines[:idx_start] + new_lines + lines[idx_end:]
                result_content = "".join(result_lines)

                # ---- Validate the resulting full file content ----
                guard_error = _validate_and_guard(file_path, result_content)
                if guard_error:
                    return guard_error

                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(result_content)

            return f"[SUCCESS] Edited lines {start_line}-{end_line} of {file_path}."
        except Exception as e:
            return f"[FAILED] {str(e)}"


class InsertAtLineTool:
    name: str = "insert_at_line"
    description: str = (
        "Inserts content at a specific line number (before the existing line). Use this to add code at a specific position without affecting existing lines."
    )
    args_schema = InsertAtLineSchema

    def __init__(
        self,
        workspace_path: str,
        require_approval: bool = False,
        approval_callback: Any = None,
    ):
        self.workspace_path = workspace_path
        self.require_approval = require_approval
        self.approval_callback = approval_callback

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, file_path: str, line_number: int, content: str) -> str:
        if self.require_approval and self.approval_callback:
            try:
                msg = f"INSERT_AT_LINE: {file_path}\nLINE: {line_number}\n\nCONTENT PREVIEW:\n{content[:100]}..."
                approved, feedback = self.approval_callback(msg)
                if not approved:
                    return f"[REJECTED] {feedback}"
            except InterruptedError:
                return "[SYSTEM] Aborted."

        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            workspace_abs = os.path.abspath(self.workspace_path) + os.sep
            if not (target_path + os.sep).startswith(workspace_abs):
                return "[DENIED] Outside workspace."

            if not os.path.exists(target_path):
                return "[FAILED] Not found."

            with _get_file_lock(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                idx = line_number - 1
                if idx < 0:
                    idx = 0
                if idx > len(lines):
                    idx = len(lines)

                new_lines = content.splitlines(keepends=True)
                if content and not content.endswith("\n"):
                    new_lines[-1] = new_lines[-1] + "\n"

                result_lines = lines[:idx] + new_lines + lines[idx:]
                result_content = "".join(result_lines)

                # ---- Validate the resulting full file content ----
                guard_error = _validate_and_guard(file_path, result_content)
                if guard_error:
                    return guard_error

                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(result_content)

            return f"[SUCCESS] Inserted content at line {line_number} of {file_path}."
        except Exception as e:
            return f"[FAILED] {str(e)}"


class BatchReplaceFileContentTool:
    name: str = "batch_replace_file_content"
    description: str = (
        "Transactional multi-chunk replacement for a single file. PREFERRED over multiple replace_in_file calls.\n"
        "Provide a list of {target_content, replacement_content} chunks. Rules:\n"
        "  1. Each target_content must appear EXACTLY ONCE in the file — ambiguous or missing anchors abort the whole transaction.\n"
        "  2. Chunks are applied bottom-to-top (by position) to prevent line-drift corruption.\n"
        "  3. If any chunk fails OR the result fails syntax validation, ALL changes are rolled back and the file is left untouched.\n"
        "Use this for surgical multi-site edits to JS, TS, TSX, CSS, HTML, or Python files."
    )
    args_schema = BatchReplaceFileContentSchema

    def __init__(
        self,
        workspace_path: str,
        require_approval: bool = False,
        approval_callback: Any = None,
    ):
        self.workspace_path = workspace_path
        self.require_approval = require_approval
        self.approval_callback = approval_callback

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, file_path: str, chunks: list[dict]) -> str:
        if self.require_approval and self.approval_callback:
            try:
                preview = f"BATCH_REPLACE: {file_path}\n{len(chunks)} chunk(s):\n"
                for i, c in enumerate(chunks[:3]):
                    preview += f"  [{i+1}] target={str(c.get('target_content',''))[:60]}...\n"
                approved, feedback = self.approval_callback(preview)
                if not approved:
                    reason = feedback.strip() if feedback else "No specific reason provided."
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user REJECTED this batch edit.\nThey said: '{reason}'.\nDo NOT try this again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."

        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            workspace_abs = os.path.abspath(self.workspace_path) + os.sep
            if not (target_path + os.sep).startswith(workspace_abs):
                return "[SYSTEM] Access denied. You can only edit files inside the workspace directory."

            if not os.path.exists(target_path):
                return f"[FAILED] File not found: {file_path}"

            if not chunks:
                return "[FAILED] No chunks provided. Nothing to do."

            with _get_file_lock(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    original_content = f.read()

                working_content = original_content

                # ------------------------------------------------------------------
                # Phase 1: Validate all anchors on the ORIGINAL content first.
                # We locate each anchor's position so we can sort bottom-to-top.
                # ------------------------------------------------------------------
                anchor_positions: list[tuple[int, int, dict]] = []  # (start, end, chunk)

                for i, chunk in enumerate(chunks):
                    target = chunk.get("target_content", "")
                    replacement = chunk.get("replacement_content", "")

                    if not target:
                        return f"[FAILED] Chunk {i+1} has an empty target_content. Transaction rolled back. File unchanged."

                    count = working_content.count(target)
                    if count == 0:
                        return (
                            f"[FAILED] Chunk {i+1} anchor not found in {file_path}.\n"
                            f"  Expected to find: {target[:120]!r}\n"
                            f"Transaction rolled back. File unchanged. Use Read File to verify current content."
                        )
                    if count > 1:
                        return (
                            f"[FAILED] Chunk {i+1} anchor is ambiguous — found {count} occurrences in {file_path}.\n"
                            f"  Ambiguous text: {target[:120]!r}\n"
                            f"Provide a more unique target_content. Transaction rolled back. File unchanged."
                        )

                    start = working_content.index(target)
                    end = start + len(target)
                    anchor_positions.append((start, end, chunk))

                # ------------------------------------------------------------------
                # Phase 2: Sort descending by position (bottom-to-top application).
                # This prevents earlier replacements from shifting offsets of later ones.
                # ------------------------------------------------------------------
                anchor_positions.sort(key=lambda x: x[0], reverse=True)

                # ------------------------------------------------------------------
                # Phase 3: Apply replacements on a fresh copy of original content.
                # ------------------------------------------------------------------
                result_content = original_content
                for start, end, chunk in anchor_positions:
                    target = chunk["target_content"]
                    replacement = chunk.get("replacement_content", "")
                    result_content = result_content[:start] + replacement + result_content[end:]

                # ------------------------------------------------------------------
                # Phase 4: Syntax / size validation on final result.
                # ------------------------------------------------------------------
                guard_error = _validate_and_guard(file_path, result_content)
                if guard_error:
                    return f"{guard_error}\nTransaction rolled back. File unchanged."

                # ------------------------------------------------------------------
                # Phase 5: Commit.
                # ------------------------------------------------------------------
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(result_content)

            return (
                f"[SUCCESS] Applied {len(chunks)} chunk(s) to {file_path}. "
                f"File updated ({len(original_content)} → {len(result_content)} chars)."
            )

        except Exception as e:
            return f"[FAILED] Error in batch_replace_file_content: {str(e)}"


class ReportTaskStatusTool:
    name: str = "report_task_status"
    description: str = (
        "Call this tool BEFORE giving your Final Answer to report whether the task succeeded, failed, or partially completed.\n"
        "This is MANDATORY - always call this before finishing. IMPORTANT: Do this only AFTER verification."
    )
    args_schema = ReportTaskStatusSchema

    def __init__(self, result_holder: dict):
        self.result_holder = result_holder

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, status: str, summary: str) -> str:
        """Record the task completion status."""
        valid_statuses = ("success", "failed", "partial")
        if status not in valid_statuses:
            return (
                f"[FAILED] Invalid status '{status}'. Must be one of: {valid_statuses}"
            )

        self.result_holder["status"] = status
        self.result_holder["summary"] = summary
        return f"[SUCCESS] Task status recorded as '{status}': {summary}"


# ==================================
# TOOL REGISTRY
# ==================================


class ToolRegistry:
    """Maps tool names to callable tool instances, and exports OpenAI-format schemas.

    Usage:
        registry = ToolRegistry([terminal_tool, write_tool, read_tool, ...])
        schemas = registry.get_schemas()      # pass to litellm tools=
        result = registry.execute("write_file", {"file_path": "...", "content": "..."})
    """

    def __init__(self, tools: list):
        self._tools = {tool.name: tool for tool in tools}

    def get_schemas(self) -> list[dict]:
        """Return list of OpenAI function-calling schemas for all registered tools."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_tool(self, name: str):
        return self._tools.get(name)

    def execute(self, tool_name: str, args: dict) -> str:
        """Dispatch a tool call by name with the given arguments dict."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return f"[FAILED] Unknown tool: '{tool_name}'. Available tools: {list(self._tools.keys())}"
        try:
            # Validate args against the Pydantic schema
            validated = tool.args_schema(**args)
            return tool.run(**validated.model_dump())
        except Exception as e:
            return f"[FAILED] Tool '{tool_name}' error: {str(e)}"


def create_dev_tool_registry(
    workspace_path: str,
    require_approval: bool,
    approval_callback: Any,
    stream_callback: Any,
    task_status: dict,
) -> ToolRegistry:
    """Factory that creates the standard dev tool registry.

    Replaces the old create_dev_tools() list factory — same tools,
    now wrapped in a ToolRegistry for schema export and name-based dispatch.
    """
    tools = [
        TerminalExecutionTool(
            workspace_path=workspace_path,
            require_approval=require_approval,
            approval_callback=approval_callback,
            stream_callback=stream_callback,
        ),
        WriteFileTool(
            workspace_path=workspace_path,
            require_approval=require_approval,
            approval_callback=approval_callback,
        ),
        ReadFileTool(workspace_path=workspace_path),
        ReplaceInFileTool(
            workspace_path=workspace_path,
            require_approval=require_approval,
            approval_callback=approval_callback,
        ),
        EditFileLinesTool(
            workspace_path=workspace_path,
            require_approval=require_approval,
            approval_callback=approval_callback,
        ),
        InsertAtLineTool(
            workspace_path=workspace_path,
            require_approval=require_approval,
            approval_callback=approval_callback,
        ),
        BatchReplaceFileContentTool(
            workspace_path=workspace_path,
            require_approval=require_approval,
            approval_callback=approval_callback,
        ),
        ReportTaskStatusTool(result_holder=task_status),
    ]
    return ToolRegistry(tools)
