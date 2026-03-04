import os
import subprocess
import threading
from typing import Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class TerminalExecutionSchema(BaseModel):
    command: str = Field(description="The shell command to execute, e.g. 'npm install next' or 'mkdir src'.")

class WriteFileSchema(BaseModel):
    file_path: str = Field(description="The relative path to the file to create or overwrite, e.g. 'src/App.tsx'")
    content: str = Field(description="The complete code/text content to write to the file.")

class TerminalExecutionTool(BaseTool):
    name: str = "Execute Terminal Command"
    description: str = "Executes a shell command in the specified workspace directory and returns the stdout and stderr."
    args_schema: type[BaseModel] = TerminalExecutionSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None
    stream_callback: Any = None  # Called with (stream_type, line) for real-time output

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path
        
        # Ensure the workspace directory actually exists
        if not os.path.exists(self.workspace_path):
            os.makedirs(self.workspace_path, exist_ok=True)

    def _run(self, command: str) -> str:
        """Execute the command using Popen with real-time streaming"""
        
        if self.require_approval and self.approval_callback:
            try:
                approved, feedback = self.approval_callback(command)
                if not approved:
                    reason = feedback.strip() if feedback else "No specific reason provided."
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user (your manager) explicitly REJECTED this command.\nThey said: '{reason}'.\nDo NOT run this command again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."

        try:
            cwd = os.path.abspath(self.workspace_path)
            
            # Notify stream that command is starting
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
                bufsize=1  # Line-buffered
            )
            
            stdout_lines = []
            stderr_lines = []
            
            def read_stream(pipe, collector, stream_type):
                """Read lines from a pipe and stream them in real-time."""
                try:
                    for line in iter(pipe.readline, ''):
                        if line:
                            collector.append(line)
                            if self.stream_callback:
                                self.stream_callback(stream_type, line.rstrip('\n\r'))
                except (ValueError, OSError):
                    pass  # Pipe closed
                finally:
                    pipe.close()
            
            # Start reader threads for both stdout and stderr
            stdout_thread = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines, "stdout"))
            stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines, "stderr"))
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process with timeout
            try:
                proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                if self.stream_callback:
                    self.stream_callback("stderr", "[TIMEOUT] Command killed after 300 seconds.")
                return "Command execution timed out after 300 seconds."
            
            # Wait for reader threads to finish
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            
            returncode = proc.returncode
            stdout_text = ''.join(stdout_lines)
            stderr_text = ''.join(stderr_lines)
            
            # Notify stream that command finished
            if self.stream_callback:
                self.stream_callback("cmd_end", {"exit_code": returncode, "success": returncode == 0})
            
            # Build return string for CrewAI
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
    description: str = "Writes content to a file in the workspace directory. Automatically creates parent directories if they don't exist."
    args_schema: type[BaseModel] = WriteFileSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path
        
    def _run(self, file_path: str, content: str) -> str:
        """Write content to a file safely within the workspace."""
        
        if self.require_approval and self.approval_callback:
            try:
                # Truncate content for the UI popup so it doesn't flood the action block
                display_content = content[:200] + ("..." if len(content) > 200 else "")
                approved, feedback = self.approval_callback(f"WRITE_FILE: {file_path}\n\nCONTENT PREVIEW:\n{display_content}")
                if not approved:
                    reason = feedback.strip() if feedback else "No specific reason provided."
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user explicitly REJECTED writing to this file.\nThey said: '{reason}'.\nDo NOT try this again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."
                
        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            # Basic jail check
            if not target_path.startswith(os.path.abspath(self.workspace_path)):
                return "[SYSTEM] Access denied. You can only write files inside the workspace directory."
                
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"[SUCCESS] File written successfully to {file_path}"
        except Exception as e:
            return f"[FAILED] Error writing file: {str(e)}"

class ReadFileSchema(BaseModel):
    file_path: str = Field(description="The relative path to the file to read, e.g. 'src/App.tsx'")
    start_line: int = Field(default=0, description="Optional starting line number (0-based). Use 0 to start from the beginning.")
    end_line: int = Field(default=-1, description="Optional ending line number (0-based, inclusive). Use -1 to read to the end.")

class ReadFileTool(BaseTool):
    name: str = "Read File"
    description: str = "Reads the content of a file in the workspace. You can optionally specify a line range. Use this BEFORE editing files to understand their current content."
    args_schema: type[BaseModel] = ReadFileSchema
    workspace_path: str = "./workspace"

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(self, file_path: str, start_line: int = 0, end_line: int = -1) -> str:
        """Read file content, optionally a specific line range."""
        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            if not target_path.startswith(os.path.abspath(self.workspace_path)):
                return "[SYSTEM] Access denied. You can only read files inside the workspace directory."
            
            if not os.path.exists(target_path):
                return f"[FAILED] File not found: {file_path}"
            
            with open(target_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            if end_line == -1:
                end_line = total_lines - 1
            
            # Clamp to valid range
            start_line = max(0, min(start_line, total_lines - 1))
            end_line = max(start_line, min(end_line, total_lines - 1))
            
            selected = lines[start_line:end_line + 1]
            
            # Number lines so the agent knows exact positions
            numbered = ""
            for i, line in enumerate(selected):
                numbered += f"{start_line + i + 1:4d} | {line}"
            
            return f"[SUCCESS] {file_path} ({total_lines} lines total, showing {start_line + 1}-{end_line + 1})\n{numbered}"
        except Exception as e:
            return f"[FAILED] Error reading file: {str(e)}"


class ReplaceInFileSchema(BaseModel):
    file_path: str = Field(description="The relative path to the file to edit, e.g. 'src/App.tsx'")
    old_text: str = Field(description="The exact text to find and replace. Must match the file content EXACTLY, including whitespace and indentation.")
    new_text: str = Field(description="The new text to replace the old text with.")

class ReplaceInFileTool(BaseTool):
    name: str = "Replace In File"
    description: str = "Finds and replaces an exact text match in a file. Use this to edit existing files without rewriting the whole file. You MUST use the Read File tool first to see the exact content, then provide the exact old_text to match. If the old_text is not found exactly, the operation will fail."
    args_schema: type[BaseModel] = ReplaceInFileSchema
    workspace_path: str = "./workspace"
    require_approval: bool = False
    approval_callback: Any = None

    def __init__(self, workspace_path: str, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path

    def _run(self, file_path: str, old_text: str, new_text: str) -> str:
        """Replace exact text match in a file."""
        
        if self.require_approval and self.approval_callback:
            try:
                old_preview = old_text[:150] + ("..." if len(old_text) > 150 else "")
                new_preview = new_text[:150] + ("..." if len(new_text) > 150 else "")
                approved, feedback = self.approval_callback(
                    f"REPLACE_IN_FILE: {file_path}\n\nOLD TEXT:\n{old_preview}\n\nNEW TEXT:\n{new_preview}"
                )
                if not approved:
                    reason = feedback.strip() if feedback else "No specific reason provided."
                    return f"[SYSTEM MESSAGE - CRITICAL]\nThe user REJECTED this edit.\nThey said: '{reason}'.\nDo NOT try this again. Rethink your approach."
            except InterruptedError:
                return "[SYSTEM] Execution Aborted by User."
        
        try:
            target_path = os.path.abspath(os.path.join(self.workspace_path, file_path))
            if not target_path.startswith(os.path.abspath(self.workspace_path)):
                return "[SYSTEM] Access denied. You can only edit files inside the workspace directory."
            
            if not os.path.exists(target_path):
                return f"[FAILED] File not found: {file_path}"
            
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            count = content.count(old_text)
            if count == 0:
                return f"[FAILED] Could not find the exact text to replace in {file_path}. Make sure you're matching the file content exactly, including whitespace. Use Read File to check the current content."
            
            if count > 1:
                return f"[FAILED] Found {count} occurrences of the text in {file_path}. Please provide a more specific/unique text snippet to match exactly one location."
            
            new_content = content.replace(old_text, new_text, 1)
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return f"[SUCCESS] Replaced text in {file_path}. {len(old_text)} chars replaced with {len(new_text)} chars."
        except Exception as e:
            return f"[FAILED] Error editing file: {str(e)}"

