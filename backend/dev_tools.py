import os
import subprocess
import threading
from typing import Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

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


class TerminalExecutionTool(BaseTool):
    name: str = "Execute Terminal Command"
    description: str = (
        "Executes a shell command in the specified workspace directory and returns the stdout and stderr.\n"
        "ENVIRONMENT: You are on Windows (cmd/PowerShell) - use Windows commands. NEVER run recursive directory listings like 'dir /s'. Use 'dir' (without /s).\n"
        "When scaffolding projects, ALWAYS use non-interactive flags (e.g. 'npx -y ...', 'npm init -y'). NEVER run interactive prompts.\n"
        "PRE-COMPLETION VERIFICATION: Test-run the application before finishing to verify it works (e.g. 'npm run dev' with a timeout), fix any errors, and kill the dev server."
    )
    args_schema: type[BaseModel] = TerminalExecutionSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None
    stream_callback: Any = None  # Called with (stream_type, line) for real-time output

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path, exist_ok=True)

    def _run(self, command: str) -> str:
        """Execute the command using Popen with real-time streaming"""

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

            try:
                proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                if self.stream_callback:
                    self.stream_callback(
                        "stderr", "[TIMEOUT] Command killed after 300 seconds."
                    )
                return "Command execution timed out after 300 seconds."

            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            returncode = proc.returncode
            stdout_text = "".join(stdout_lines)
            stderr_text = "".join(stderr_lines)

            if self.stream_callback:
                self.stream_callback(
                    "cmd_end", {"exit_code": returncode, "success": returncode == 0}
                )

            # Truncate output to avoid wasting tokens on massive listings
            MAX_OUTPUT = 5000
            if len(stdout_text) > MAX_OUTPUT:
                stdout_text = (
                    stdout_text[:MAX_OUTPUT]
                    + f"\n\n... [OUTPUT TRUNCATED — {len(''.join(stdout_lines))} chars total, showing first {MAX_OUTPUT}. Avoid recursive listings like 'dir /s' or 'tree'.]"
                )
            if len(stderr_text) > MAX_OUTPUT:
                stderr_text = (
                    stderr_text[:MAX_OUTPUT]
                    + f"\n\n... [STDERR TRUNCATED — {len(''.join(stderr_lines))} chars total.]"
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


class WriteFileTool(BaseTool):
    name: str = "Write File"
    description: str = (
        "Writes content to a file in the workspace directory. Automatically creates parent directories if they don't exist.\n"
        "ALWAYS use this tool to save NEW source code. Do NOT use echo or cat to write blocks of code in the terminal."
    )
    args_schema: type[BaseModel] = WriteFileSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(self, file_path: str, content: str) -> str:
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

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[SUCCESS] File written successfully to {file_path}"
        except Exception as e:
            return f"[FAILED] Error writing file: {str(e)}"


class ReadFileTool(BaseTool):
    name: str = "Read File"
    description: str = (
        "Reads the content of a file in the workspace. You can optionally specify a line range.\n"
        "When you need to EDIT an existing file, you MUST ALWAYS use Read File first to see the current content and exact line numbers."
    )
    args_schema: type[BaseModel] = ReadFileSchema
    workspace_path: str = "./workspace"

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(self, file_path: str, start_line: int = 0, end_line: int = -1) -> str:
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


class ReplaceInFileTool(BaseTool):
    name: str = "Replace In File"
    description: str = (
        "Finds and replaces an exact text match in a file. Use this if you have a unique text snippet to match without rewriting the whole file.\n"
        "You MUST use the Read File tool first to see the exact content. If the old_text is not found exactly, the operation will fail."
    )
    args_schema: type[BaseModel] = ReplaceInFileSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(self, file_path: str, old_text: str, new_text: str) -> str:
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

            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_text)
            if count == 0:
                return f"[FAILED] Could not find the exact text to replace in {file_path}. Make sure you're matching the file content exactly, including whitespace. Use Read File to check the current content."

            if count > 1:
                return f"[FAILED] Found {count} occurrences of the text in {file_path}. Please provide a more specific/unique text snippet to match exactly one location."

            new_content = content.replace(old_text, new_text, 1)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"[SUCCESS] Replaced text in {file_path}. {len(old_text)} chars replaced with {len(new_text)} chars."
        except Exception as e:
            return f"[FAILED] Error editing file: {str(e)}"


class EditFileLinesTool(BaseTool):
    name: str = "Edit File Lines"
    description: str = (
        "Replaces a specific range of lines in a file with new content. Use this for surgical edits.\n"
        "Never rewrite a whole file just to change a few lines. You MUST use Read File first to get the correct line numbers."
    )
    args_schema: type[BaseModel] = EditFileLinesSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(
        self, file_path: str, start_line: int, end_line: int, new_content: str
    ) -> str:
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

            with open(target_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            idx_start = start_line - 1
            idx_end = end_line

            if idx_start < 0 or idx_start >= len(lines) or idx_end < idx_start:
                return f"[FAILED] Invalid range {start_line}-{end_line} for file with {len(lines)} lines."

            new_lines = new_content.splitlines(keepends=True)
            if new_content and not new_content.endswith("\n"):
                new_lines[-1] = new_lines[-1] + "\n"

            lines[idx_start:idx_end] = new_lines

            with open(target_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return f"[SUCCESS] Edited lines {start_line}-{end_line} of {file_path}."
        except Exception as e:
            return f"[FAILED] {str(e)}"


class InsertAtLineTool(BaseTool):
    name: str = "Insert At Line"
    description: str = (
        "Inserts content at a specific line number (before the existing line). Use this to add code at a specific position without affecting existing lines."
    )
    args_schema: type[BaseModel] = InsertAtLineSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(self, file_path: str, line_number: int, content: str) -> str:
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

            for i, line in enumerate(new_lines):
                lines.insert(idx + i, line)

            with open(target_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return f"[SUCCESS] Inserted content at line {line_number} of {file_path}."
        except Exception as e:
            return f"[FAILED] {str(e)}"


class ReportTaskStatusTool(BaseTool):
    name: str = "Report Task Status"
    description: str = (
        "Call this tool BEFORE giving your Final Answer to report whether the task succeeded, failed, or partially completed.\n"
        "This is MANDATORY - always call this before finishing. IMPORTANT: Do this only AFTER verification."
    )
    args_schema: type[BaseModel] = ReportTaskStatusSchema
    result_holder: dict = {}

    def __init__(self, result_holder: dict, **kwargs):
        super().__init__(**kwargs)
        self.result_holder = result_holder

    def _run(self, status: str, summary: str) -> str:
        """Record the task completion status."""
        valid_statuses = ("success", "failed", "partial")
        if status not in valid_statuses:
            return (
                f"[FAILED] Invalid status '{status}'. Must be one of: {valid_statuses}"
            )

        self.result_holder["status"] = status
        self.result_holder["summary"] = summary
        return f"[SUCCESS] Task status recorded as '{status}': {summary}"
