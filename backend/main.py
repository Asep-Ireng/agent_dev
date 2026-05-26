from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os
import io
import base64
import sys
import threading
import queue
import asyncio
import traceback
import yaml
from PyPDF2 import PdfReader
from crewai import Agent, Task, Crew, LLM
from langchain_core.callbacks import BaseCallbackHandler
from fastapi.responses import StreamingResponse
from dev_tools import (
    TerminalExecutionTool,
    WriteFileTool,
    ReadFileTool,
    ReplaceInFileTool,
    EditFileLinesTool,
    InsertAtLineTool,
    ReportTaskStatusTool,
)
from design_tools import UpdateSpecTool
from dotenv import load_dotenv

# Load environment variables from root .env (single source of truth)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="AI Agent Developer Backend")

# Global event to signal the background Agent thread to abort execution
# TODO: abort_event and approval_state are process-global — concurrent requests
# will interfere. Implement per-request run_id keying if deploying multi-user.
abort_event = threading.Event()

# State for HITL execution approvals
approval_state = {"event": threading.Event(), "approved": False, "feedback": None}

# Live-toggleable approval setting (mutable dict so tools can see changes mid-run)
approval_settings = {"require": False}

# Runtime settings (loaded from .env, modifiable via API)
runtime_settings = {
    "provider": os.getenv("DEFAULT_PROVIDER", "Google (Gemini)"),
    "google_model": os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o"),
    "thinking_level": os.getenv("THINKING_LEVEL", "none"),
}

# Base workspace directory — all workspace_path values must resolve inside this
BASE_WORKSPACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "workspace")
)
os.makedirs(BASE_WORKSPACE_DIR, exist_ok=True)


class ApproveRequest(BaseModel):
    approved: bool
    feedback: str | None = None


# Allow requests from our Next.js frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================================
# HELPERS
# ==================================


def get_current_provider() -> str:
    return runtime_settings["provider"]


def get_current_model() -> str:
    provider = get_current_provider()
    if provider == "OpenAI":
        return runtime_settings["openai_model"]
    return runtime_settings["google_model"]


def get_llm(model_name: str, provider: str):
    if provider == "Google (Gemini)":
        return f"gemini/{model_name}"
    return model_name


def set_keys_from_env():
    """Set API keys in environment from loaded .env values."""
    provider = get_current_provider()
    if provider == "OpenAI":
        key = os.getenv("OPENAI_API_KEY", "")
        if key:
            os.environ["OPENAI_API_KEY"] = key
    elif provider == "Google (Gemini)":
        key = os.getenv("GOOGLE_API_KEY", "")
        if key:
            os.environ["GEMINI_API_KEY"] = key
            os.environ["GOOGLE_API_KEY"] = key


def validate_workspace_path(workspace_path: str) -> str:
    """Validate and normalize workspace_path. Returns absolute path or raises HTTPException."""
    resolved = os.path.abspath(workspace_path)
    base_with_sep = BASE_WORKSPACE_DIR + os.sep
    if resolved != BASE_WORKSPACE_DIR and not resolved.startswith(base_with_sep):
        raise HTTPException(status_code=400, detail="Invalid workspace path.")
    return resolved


def validate_chat_history(history_json: str) -> list:
    """Parse and validate chat history JSON. Returns list of validated messages."""
    import json as _json_mod

    MAX_CONTENT_LENGTH = 4000
    ALLOWED_ROLES = {"user", "assistant"}

    if not history_json:
        return []

    try:
        parsed = _json_mod.loads(history_json)
    except _json_mod.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid chat history JSON.")

    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="Chat history must be a list.")

    validated = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "")
        content = item.get("content", "")
        if role not in ALLOWED_ROLES or not isinstance(content, str):
            continue
        validated.append({"role": role, "content": content[:MAX_CONTENT_LENGTH]})

    return validated


# Set keys on startup
set_keys_from_env()


# ==================================
# API ROUTES & MODELS
# ==================================


class DesignRequest(BaseModel):
    idea: str


class DevelopRequest(BaseModel):
    spec: str
    workspace_path: str = BASE_WORKSPACE_DIR
    require_approval: bool = False


class IterateRequest(BaseModel):
    task: str = ""
    spec: str = ""
    dev_context: str = ""
    workspace_path: str = BASE_WORKSPACE_DIR
    require_approval: bool = False


class SettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    thinking_level: str | None = None


# ==================================
# SETTINGS ENDPOINTS
# ==================================


@app.get("/api/settings")
async def get_settings():
    """Returns current runtime config (no secrets)."""
    return {
        "provider": get_current_provider(),
        "model": get_current_model(),
        "google_model": runtime_settings["google_model"],
        "openai_model": runtime_settings["openai_model"],
        "thinking_level": runtime_settings["thinking_level"],
        "available_providers": ["OpenAI", "Google (Gemini)"],
        "workspace_path": BASE_WORKSPACE_DIR,
    }


@app.post("/api/settings")
async def update_settings(req: SettingsUpdate):
    """Update provider/model at runtime (no secrets involved)."""
    if req.provider is not None:
        if req.provider not in ["OpenAI", "Google (Gemini)"]:
            raise HTTPException(status_code=400, detail="Unknown provider.")
        runtime_settings["provider"] = req.provider
        set_keys_from_env()  # Re-apply keys for new provider
    if req.model is not None:
        provider = get_current_provider()
        if provider == "OpenAI":
            runtime_settings["openai_model"] = req.model
        else:
            runtime_settings["google_model"] = req.model
    if req.thinking_level is not None:
        runtime_settings["thinking_level"] = req.thinking_level
    return {
        "status": "ok",
        "provider": get_current_provider(),
        "model": get_current_model(),
        "thinking_level": runtime_settings["thinking_level"],
    }


@app.get("/api/workspace/diff")
async def get_workspace_diff(workspace_path: str = BASE_WORKSPACE_DIR):
    import subprocess
    try:
        ws = validate_workspace_path(workspace_path)
        res = subprocess.run(
            "git diff --relative",
            shell=True,
            cwd=ws,
            text=True,
            capture_output=True,
        )
        return {"diff": res.stdout}
    except Exception as e:
        return {"diff": "", "error": str(e)}


@app.post("/api/design/chat")
async def generate_design_chat(
    idea: str = Form(...), spec: str = Form(""), files: List[UploadFile] = File(None)
):
    try:
        set_keys_from_env()
        provider = get_current_provider()
        model = get_current_model()

        # 1. Process Uploaded Files
        file_context = ""
        image_urls = []

        if files:
            for file in files:
                contents = await file.read()

                # Extract PDF text
                if file.filename.lower().endswith(".pdf"):
                    pdf_reader = PdfReader(io.BytesIO(contents))
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    file_context += (
                        f"\n--- PDF Extracted Content: {file.filename} ---\n{text}\n"
                    )

                # Encode Images to Base64 (Useful if model natively supports data URLs in CrewAI)
                elif file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    base64_image = base64.b64encode(contents).decode("utf-8")
                    mime_type = file.content_type
                    data_url = f"data:{mime_type};base64,{base64_image}"
                    image_urls.append(data_url)
                    file_context += (
                        f"\n--- Image Uploaded: {file.filename} (passed natively) ---\n"
                    )

        # 2. Build the Prompt Context
        context_prompt = f"User Request / Idea: {idea}\n\n"
        if spec:
            context_prompt += f"CURRENT SPECIFICATION (Edit this based on the user's new request):\n{spec}\n\n"
        if file_context:
            context_prompt += f"ATTACHED FILE CONTEXT:\n{file_context}\n\n"

        # Shared dict for the UpdateSpecTool to write into
        spec_result = {}
        update_spec_tool = UpdateSpecTool(result_holder=spec_result)

        with open(os.path.join(os.path.dirname(__file__), "config", "agents.yaml"), "r", encoding="utf-8") as f:
            agents_config = yaml.safe_load(f)

        designer = Agent(
            **agents_config["designer"],
            verbose=True,
            allow_delegation=False,
            llm=get_llm(model, provider),
            tools=[update_spec_tool],
        )

        design_task = Task(
            description=f'Read the following constraints and current state, then create or update the specification. Use the "Update Specification" tool to save the spec and describe what changed.\n\n{context_prompt}',
            expected_output="The specification should be saved via the Update Specification tool.",
            agent=designer,
        )

        crew = Crew(agents=[designer], tasks=[design_task])
        result = crew.kickoff()

        metrics = {}
        if hasattr(crew, "usage_metrics") and crew.usage_metrics:
            metrics = {
                "prompt_tokens": getattr(crew.usage_metrics, "prompt_tokens", 0),
                "completion_tokens": getattr(crew.usage_metrics, "completion_tokens", 0),
                "total_tokens": getattr(crew.usage_metrics, "total_tokens", 0),
            }

        # Read from shared dict if tool was called, fall back to raw output
        if spec_result.get("spec"):
            return {
                "spec": spec_result["spec"],
                "summary": spec_result.get("summary", "Specification updated."),
                "usage": metrics,
            }
        else:
            raw_output = result.raw if hasattr(result, "raw") else str(result)
            return {
                "spec": raw_output,
                "summary": "Specification generated.",
                "usage": metrics,
            }

    except Exception as e:
        print(f"Server Error during Design Chat: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during design generation.",
        )


@app.post("/api/dev-chat")
async def dev_chat(
    message: str = Form(...),
    spec: str = Form(""),
    workspace_path: str = Form(BASE_WORKSPACE_DIR),
    history: str = Form("[]"),  # JSON string of [{role, content}]
    files: List[UploadFile] = File(default=[]),
):
    """Chat with the dev agent about the code it built, with optional image attachments."""
    set_keys_from_env()
    provider = get_current_provider()
    model = get_current_model()

    try:
        import litellm

        # Validate inputs
        ws = validate_workspace_path(workspace_path)
        chat_history_raw = validate_chat_history(history)

        # Filter and cap history to prevent token explosion (e.g. recursive build results)
        chat_history = []
        for msg in chat_history_raw:
            content = msg["content"]
            # Skip massive changes-applied logs or UI control messages in LLM history
            if (
                content.startswith("✅ **Changes Applied:**")
                or content.startswith("▶ Proceeding")
                or content.startswith("✕ Cancelled")
            ):
                continue
            # Keep only a preview of the proposed plan if it's too long
            if content.startswith("**📋 Proposed Plan:**"):
                content = content[:1000] + "\n\n... [Plan truncated for chat history brevity] ..."
            chat_history.append({"role": msg["role"], "content": content})

        # Only take the last 8 messages for context
        chat_history = chat_history[-8:]

        # Scan the workspace for a file tree to give the agent context
        file_tree = []
        if os.path.exists(ws):
            for root, dirs, files_list in os.walk(ws):
                dirs[:] = [
                    d
                    for d in dirs
                    if d
                    not in (
                        "node_modules",
                        ".git",
                        "__pycache__",
                        ".next",
                        "dist",
                        "build",
                        ".venv",
                        "venv",
                    )
                ]
                for fname in files_list:
                    rel = os.path.relpath(os.path.join(root, fname), ws)
                    file_tree.append(rel)

        tree_str = "\n".join(file_tree[:100])
        if len(file_tree) > 100:
            tree_str += f"\n... and {len(file_tree) - 100} more files"

        system_prompt = f"""You are the developer who just built an application. You built it according to this spec:

---
{spec}
---

The project is at: {ws}

File tree:
{tree_str}

You can discuss:
- Design decisions and why you made them
- Library choices and alternatives
- Code structure and architecture
- Bugs or issues the user points out
- Suggestions for improvements

If the user attaches screenshots, analyze what you see and provide specific feedback.
If the user asks about specific file contents, tell them which file to look at and what to expect there.
Keep responses concise and useful. Use markdown formatting."""

        messages = [{"role": "system", "content": system_prompt}]

        # Add validated chat history
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Build the current user message — may include images
        user_content = []
        user_content.append({"type": "text", "text": message})

        # Process uploaded images
        if files:
            for file in files:
                contents = await file.read()
                if file.filename and file.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp", ".gif")
                ):
                    b64 = base64.b64encode(contents).decode("utf-8")
                    mime = file.content_type or "image/png"
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        }
                    )

        # Use multimodal format if images are attached, plain text otherwise
        if len(user_content) == 1:
            messages.append({"role": "user", "content": message})
        else:
            messages.append({"role": "user", "content": user_content})

        model_str = get_llm(model, provider)
        response = litellm.completion(model=model_str, messages=messages)

        reply = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        usage_dict = {}
        if usage:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }
        return {"reply": reply, "usage": usage_dict}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Server Error during Dev Chat: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred during dev chat."
        )


import json as _json
import re as _re


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and naked color codes from CrewAI/langchain output."""
    text = _re.sub(r"\x1b\[[0-9;]*[mGKF]", "", text)
    text = _re.sub(r"\[\d+m", "", text)
    return text.strip()


def _emit(q: queue.Queue, event_type: str, payload: dict):
    """Helper to push a typed SSE event onto the queue."""
    q.put(f"event: {event_type}\ndata: {_json.dumps(payload)}\n\n")


class CustomStreamCallback(BaseCallbackHandler):
    """Callback handler that forwards LLM reasoning/thinking tokens to the SSE queue.
    
    Only emits reasoning_content chunks (extended thinking) — not regular output tokens.
    Regular token streaming is handled by PatchedStream intercepting litellm's response.
    """
    def __init__(self, q: queue.Queue):
        self.q = q

    def on_llm_end(self, response, **kwargs) -> None:
        """No-op — token forwarding is done by PatchedStream."""
        pass


import litellm as _litellm

_thread_local = threading.local()
_old_completion = _litellm.completion

class PatchedStream:
    def __init__(self, response):
        self.response = response

    def __iter__(self):
        return self

    def __next__(self):
        try:
            chunk = next(self.response)
        except StopIteration:
            raise StopIteration

        try:
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                if hasattr(_thread_local, "queue") and _thread_local.queue:
                    _emit(_thread_local.queue, "model_thinking", {"text": delta.reasoning_content})
        except Exception:
            pass

        return chunk

    def __getattr__(self, name):
        return getattr(self.response, name)


def _patched_completion(*args, **kwargs):
    response = _old_completion(*args, **kwargs)
    if kwargs.get("stream"):
        return PatchedStream(response)
    # Non-streaming: extract reasoning_content (Gemini extended thinking)
    try:
        if hasattr(_thread_local, "queue") and _thread_local.queue:
            msg = response.choices[0].message
            reasoning = getattr(msg, "reasoning_content", None)
            if reasoning:
                _emit(_thread_local.queue, "model_thinking", {"text": reasoning})
    except Exception:
        pass
    return response

_litellm.completion = _patched_completion


class StreamCatcher:
    """Captures CrewAI stdout, parses ReAct patterns, and emits typed SSE events.

    Designed to be assigned to sys.stdout inside a background thread so that
    all CrewAI print output is intercepted, parsed, and forwarded as structured
    SSE events via the provided queue.
    """

    def __init__(self, q: queue.Queue):
        self.q = q
        self.buffer = ""
        self.in_thinking = False

    def write(self, text):
        if not text or not text.strip():
            return

        clean = _strip_ansi(text)
        if not clean:
            return

        if "<think>" in clean:
            self.in_thinking = True
            clean = clean.replace("<think>", "").strip()
            if not clean:
                return

        if "</think>" in clean:
            self.in_thinking = False
            clean = clean.replace("</think>", "").strip()
            if clean:
                _emit(self.q, "model_thinking", {"text": clean})
            return

        if self.in_thinking:
            _emit(self.q, "model_thinking", {"text": clean})
            return

        # --- Detect CrewAI ReAct patterns ---

        # Agent start / delegation header
        if clean.startswith("Agent:") or clean.startswith("## Agent:"):
            _emit(self.q, "system", {"text": clean, "level": "info"})
            return

        # Task header
        if clean.startswith("Task:") or clean.startswith("## Task:"):
            _emit(self.q, "system", {"text": clean, "level": "info"})
            return

        # Agent thinking / reasoning
        if clean.startswith("Thought:") or clean.startswith("> Thinking:"):
            thought_text = clean.split(":", 1)[1].strip() if ":" in clean else clean
            _emit(self.q, "thought", {"text": thought_text})
            return

        # Tool call detection
        if clean.startswith("Action:"):
            tool_name = clean.split(":", 1)[1].strip() if ":" in clean else clean
            _emit(self.q, "tool_call", {"tool": tool_name, "input": ""})
            return

        if clean.startswith("Action Input:"):
            action_input = clean.split(":", 1)[1].strip() if ":" in clean else clean
            _emit(self.q, "tool_input", {"input": action_input})
            return

        # Tool result / observation — parse structured markers from our tools
        if (
            clean.startswith("Observation:")
            or ("Tool" in clean and "executed with result" in clean)
        ):
            self._emit_tool_result(clean)
            return

        # Final answer
        if clean.startswith("Final Answer:"):
            answer_text = clean.split(":", 1)[1].strip() if ":" in clean else clean
            _emit(self.q, "final_answer", {"text": answer_text})
            return

        # System messages from our own code
        if clean.startswith("[SYSTEM]"):
            level = "info"
            if "[WARN]" in clean:
                level = "warn"
            elif "[ERROR]" in clean:
                level = "error"
            _emit(self.q, "system", {"text": clean, "level": level})
            return

        # Everything else — send as raw log
        _emit(self.q, "log", {"text": clean})

    def _emit_tool_result(self, text):
        """Parse tool result text and emit structured tool_result event."""
        result_text = text
        if ":" in text:
            result_text = text.split(":", 1)[1].strip()

        # Extract structured markers from our TerminalExecutionTool output
        cwd = ""
        cmd = ""
        stdout = ""
        stderr = ""
        exit_code = None
        success = True

        if "[CWD]" in result_text:
            parts = result_text
            cwd_match = _re.search(r"\[CWD\]\s*(.+?)(?:\n|\[CMD\]|$)", parts)
            cmd_match = _re.search(
                r"\[CMD\]\s*(.+?)(?:\n|\[STDOUT\]|\[STDERR\]|\[EXIT\]|$)", parts
            )
            stdout_match = _re.search(
                r"\[STDOUT\]\s*\n?(.*?)(?:\[STDERR\]|\[EXIT\]|$)", parts, _re.DOTALL
            )
            stderr_match = _re.search(
                r"\[STDERR\]\s*\n?(.*?)(?:\[EXIT\]|$)", parts, _re.DOTALL
            )
            exit_match = _re.search(r"\[EXIT\]\s*(\d+)", parts)

            if cwd_match:
                cwd = cwd_match.group(1).strip()
            if cmd_match:
                cmd = cmd_match.group(1).strip()
            if stdout_match:
                stdout = stdout_match.group(1).strip()
            if stderr_match:
                stderr = stderr_match.group(1).strip()
            if exit_match:
                exit_code = int(exit_match.group(1))

            success = "[SUCCESS]" in result_text or exit_code == 0

            _emit(
                self.q,
                "tool_result",
                {
                    "tool": "terminal",
                    "cwd": cwd,
                    "cmd": cmd,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "success": success,
                    "raw": "",
                },
            )
        elif "WRITE_FILE" in result_text or "File written" in result_text:
            success = "[SUCCESS]" in result_text
            _emit(
                self.q,
                "tool_result",
                {
                    "tool": "write_file",
                    "cwd": "",
                    "cmd": "",
                    "stdout": result_text,
                    "stderr": "",
                    "exit_code": 0 if success else 1,
                    "success": success,
                    "raw": "",
                },
            )
        else:
            # Generic tool result
            success = "[FAILED]" not in result_text and "Error" not in result_text
            _emit(
                self.q,
                "tool_result",
                {
                    "tool": "unknown",
                    "cwd": "",
                    "cmd": "",
                    "stdout": result_text,
                    "stderr": "",
                    "exit_code": 0 if success else 1,
                    "success": success,
                    "raw": result_text,
                },
            )

    def flush(self):
        pass


def create_dev_tools(workspace_path, require_approval, approval_callback, stream_callback, task_status):
    """Factory to create the standard set of developer tools.

    Used by both /api/develop and /api/dev-iterate to avoid duplicating
    the tool instantiation block.
    """
    return [
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
        ReportTaskStatusTool(result_holder=task_status),
    ]


@app.post("/api/develop")
async def generate_code_stream(req: DevelopRequest):
    set_keys_from_env()
    provider = get_current_provider()
    model = get_current_model()
    workspace_path = validate_workspace_path(req.workspace_path)
    require_approval = req.require_approval
    spec = req.spec

    # Reset the abort event before starting a new run
    abort_event.clear()
    approval_settings["require"] = require_approval

    q = queue.Queue()

    def run_crew():
        _thread_local.queue = q
        killed = False
        errored = False
        task_status = {}  # Shared dict for ReportTaskStatusTool
        error_count = [0]  # Mutable counter for step callback tracking
        old_stdout = sys.stdout
        # TODO: sys.stdout is process-global — concurrent threads will jumble output.
        # Consider hooking into CrewAI's callback system or using thread-local redirection.
        sys.stdout = StreamCatcher(q)
        try:
            _emit(
                q,
                "system",
                {"text": "Initializing Developer Agent...", "level": "info"},
            )

            def raw_approval_callback(command: str) -> tuple[bool, str | None]:
                # Notify frontend that an action needs approval
                q.put(
                    f"event: action_required\ndata: {_json.dumps({'command': command})}\n\n"
                )

                # Clear the event and wait for the user to hit the approve/reject endpoint
                approval_state["event"].clear()

                # Wait loop so we can still bail quickly if STOP is hit
                while not approval_state["event"].is_set() and not abort_event.is_set():
                    approval_state["event"].wait(0.5)

                if abort_event.is_set():
                    raise InterruptedError(
                        "User triggered manual stop while waiting for approval."
                    )

                return (approval_state["approved"], approval_state.get("feedback"))

            def approval_callback(command: str) -> tuple[bool, str | None]:
                """Wrapper that checks the live approval setting before prompting."""
                if not approval_settings["require"]:
                    return (True, None)  # Auto-approve when disabled mid-run
                return raw_approval_callback(command)

            def stream_callback(event_type, data):
                """Stream subprocess output to frontend in real-time."""
                if event_type == "cmd_start":
                    _emit(q, "cmd_start", data)
                elif event_type == "cmd_end":
                    _emit(q, "cmd_end", data)
                elif event_type in ("stdout", "stderr"):
                    _emit(q, "cmd_output", {"stream": event_type, "line": data})

            tools = create_dev_tools(
                workspace_path, require_approval, approval_callback, stream_callback, task_status
            )

            def check_abort(step_output):
                if abort_event.is_set():
                    _emit(
                        q,
                        "system",
                        {
                            "text": "Abort signal received. Terminating...",
                            "level": "warn",
                        },
                    )
                    raise InterruptedError("User triggered manual stop.")
                # Track tool failures from step output
                output_str = str(step_output) if step_output else ""
                if "[FAILED]" in output_str or "[DENIED]" in output_str:
                    error_count[0] += 1

            with open(os.path.join(os.path.dirname(__file__), "config", "agents.yaml"), "r", encoding="utf-8") as f:
                agents_config = yaml.safe_load(f)

            thinking_level = runtime_settings.get("thinking_level", "none")
            llm_kwargs = {}
            if provider == "Google (Gemini)" and thinking_level != "none" and "gemini" in model.lower():
                llm_kwargs["reasoning_effort"] = thinking_level

            my_llm = LLM(
                model=get_llm(model, provider),
                callbacks=[CustomStreamCallback(q)],
                **llm_kwargs
            )

            developer = Agent(
                **agents_config["developer"],
                verbose=True,
                allow_delegation=False,
                max_iter=75,
                llm=my_llm,
                tools=tools,
                step_callback=check_abort,
            )

            dev_task = Task(
                description=f"Read this approved spec. FIRST, create a dedicated project folder inside the workspace directory (name it based on the app name from the spec). Then build everything inside that folder. Execute terminal commands to build the file structure and write the code locally:\n\n{spec}",
                expected_output="A completely built and installed application within the workspace.",
                agent=developer,
            )

            crew = Crew(agents=[developer], tasks=[dev_task])
            crew_result = crew.kickoff()

            # Emit the final crew result as a dedicated event for the result panel
            raw_result = (
                crew_result.raw if hasattr(crew_result, "raw") else str(crew_result)
            )
            if raw_result and raw_result.strip():
                _emit(q, "result", {"text": raw_result})
        except InterruptedError as e:
            killed = True
            _emit(q, "system", {"text": f"Process stopped: {str(e)}", "level": "warn"})
        except Exception as e:
            errored = True
            _emit(q, "system", {"text": f"Build failure: {str(e)}", "level": "error"})
        finally:
            sys.stdout = old_stdout
            # Determine final status: LLM report > step tracking > exception
            if task_status.get("status"):
                final_status = task_status["status"]
            elif errored:
                final_status = "failed"
            elif killed:
                final_status = "killed"
            elif error_count[0] > 0:
                final_status = "partial"
            else:
                final_status = "success"
            metrics = {}
            if 'crew' in locals() and hasattr(crew, "usage_metrics") and crew.usage_metrics:
                metrics = {
                    "prompt_tokens": getattr(crew.usage_metrics, "prompt_tokens", 0),
                    "completion_tokens": getattr(crew.usage_metrics, "completion_tokens", 0),
                    "total_tokens": getattr(crew.usage_metrics, "total_tokens", 0),
                }
            q.put(
                f"event: done\ndata: {_json.dumps({'killed': killed, 'error': errored, 'status': final_status, 'status_summary': task_status.get('summary', ''), 'usage': metrics})}\n\n"
            )

    threading.Thread(target=run_crew).start()

    async def event_generator():
        while True:
            try:
                item = await asyncio.to_thread(q.get, timeout=0.1)
                if item:
                    yield item
                if "event: done" in item:
                    break
                if abort_event.is_set():
                    _emit(q, "system", {"text": "Stream closed.", "level": "warn"})
                    yield f"event: done\ndata: {_json.dumps({'killed': True})}\n\n"
                    break
            except queue.Empty:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/dev-iterate")
async def dev_iterate(req: IterateRequest):
    """SSE endpoint for iterative development — agent executes changes based on user instructions."""
    set_keys_from_env()
    provider = get_current_provider()
    model = get_current_model()
    workspace_path = validate_workspace_path(req.workspace_path)
    require_approval = req.require_approval
    task = req.task
    spec = req.spec
    dev_context = req.dev_context

    abort_event.clear()
    approval_settings["require"] = require_approval

    q = queue.Queue()

    def run_iterate():
        _thread_local.queue = q
        killed = False
        errored = False
        task_status = {}
        error_count = [0]
        old_stdout = sys.stdout
        # TODO: sys.stdout is process-global — concurrent threads will jumble output.
        # Consider hooking into CrewAI's callback system or using thread-local redirection.
        sys.stdout = StreamCatcher(q)
        try:
            _emit(
                q,
                "system",
                {"text": "Initializing Iteration Agent...", "level": "info"},
            )

            def raw_approval_callback(command: str) -> tuple[bool, str | None]:
                q.put(
                    f"event: action_required\ndata: {_json.dumps({'command': command})}\n\n"
                )
                approval_state["event"].clear()
                while not approval_state["event"].is_set() and not abort_event.is_set():
                    approval_state["event"].wait(0.5)
                if abort_event.is_set():
                    raise InterruptedError(
                        "User triggered manual stop while waiting for approval."
                    )
                return (approval_state["approved"], approval_state.get("feedback"))

            def approval_callback(command: str) -> tuple[bool, str | None]:
                """Wrapper that checks the live approval setting before prompting."""
                if not approval_settings["require"]:
                    return (True, None)
                return raw_approval_callback(command)

            def stream_callback(event_type, data):
                if event_type == "cmd_start":
                    _emit(q, "cmd_start", data)
                elif event_type == "cmd_end":
                    _emit(q, "cmd_end", data)
                elif event_type in ("stdout", "stderr"):
                    _emit(q, "cmd_output", {"stream": event_type, "line": data})

            tools = create_dev_tools(
                workspace_path, require_approval, approval_callback, stream_callback, task_status
            )

            def check_abort(step_output):
                if abort_event.is_set():
                    _emit(
                        q,
                        "system",
                        {
                            "text": "Abort signal received. Terminating...",
                            "level": "warn",
                        },
                    )
                    raise InterruptedError("User triggered manual stop.")
                output_str = str(step_output) if step_output else ""
                if "[FAILED]" in output_str or "[DENIED]" in output_str:
                    error_count[0] += 1

            with open(os.path.join(os.path.dirname(__file__), "config", "agents.yaml"), "r", encoding="utf-8") as f:
                agents_config = yaml.safe_load(f)

            thinking_level = runtime_settings.get("thinking_level", "none")
            llm_kwargs = {}
            if provider == "Google (Gemini)" and thinking_level != "none" and "gemini" in model.lower():
                llm_kwargs["reasoning_effort"] = thinking_level

            my_llm = LLM(
                model=get_llm(model, provider),
                callbacks=[CustomStreamCallback(q)],
                **llm_kwargs
            )

            iterator = Agent(
                **agents_config["iterative_developer"],
                verbose=True,
                allow_delegation=False,
                max_iter=50,
                llm=my_llm,
                tools=tools,
                step_callback=check_abort,
            )

            context_section = ""
            if dev_context:
                context_section = f"\n\n--- Previous Build Summary ---\nThe initial development agent produced this summary of what was built. Use this to know what files exist and where — do NOT re-read every file. Only read the specific files you need to modify.\n\n{dev_context}\n"

            iterate_task = Task(
                description=f"The user has requested the following change to the existing project:\n\n{task}\n\nFor context, here is the project spec:\n\n{spec}{context_section}\n\nOnly read the files you need to change — do NOT explore the entire project. Make the changes and verify they work.",
                expected_output="A summary of what was changed and any relevant details.",
                agent=iterator,
            )

            crew = Crew(agents=[iterator], tasks=[iterate_task])
            crew_result = crew.kickoff()

            raw_result = (
                crew_result.raw if hasattr(crew_result, "raw") else str(crew_result)
            )
            if raw_result and raw_result.strip():
                _emit(q, "result", {"text": raw_result})
        except InterruptedError as e:
            killed = True
            _emit(q, "system", {"text": f"Process stopped: {str(e)}", "level": "warn"})
        except Exception as e:
            errored = True
            _emit(
                q, "system", {"text": f"Iteration failure: {str(e)}", "level": "error"}
            )
        finally:
            sys.stdout = old_stdout
            if task_status.get("status"):
                final_status = task_status["status"]
            elif errored:
                final_status = "failed"
            elif killed:
                final_status = "killed"
            elif error_count[0] > 0:
                final_status = "partial"
            else:
                final_status = "success"
            metrics = {}
            if 'crew' in locals() and hasattr(crew, "usage_metrics") and crew.usage_metrics:
                metrics = {
                    "prompt_tokens": getattr(crew.usage_metrics, "prompt_tokens", 0),
                    "completion_tokens": getattr(crew.usage_metrics, "completion_tokens", 0),
                    "total_tokens": getattr(crew.usage_metrics, "total_tokens", 0),
                }
            q.put(
                f"event: done\ndata: {_json.dumps({'killed': killed, 'error': errored, 'status': final_status, 'status_summary': task_status.get('summary', ''), 'usage': metrics})}\n\n"
            )

    threading.Thread(target=run_iterate).start()

    async def event_generator():
        while True:
            try:
                item = await asyncio.to_thread(q.get, timeout=0.1)
                if item:
                    yield item
                if "event: done" in item:
                    break
                if abort_event.is_set():
                    _emit(q, "system", {"text": "Stream closed.", "level": "warn"})
                    yield f"event: done\ndata: {_json.dumps({'killed': True})}\n\n"
                    break
            except queue.Empty:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/develop/stop")
async def stop_development():
    """Endpoint triggered by the Stop button in the frontend Kill Switch"""
    abort_event.set()
    return {"status": "Abort signal sent."}


@app.post("/api/develop/approve")
async def approve_action(req: ApproveRequest):
    approval_state["approved"] = req.approved
    approval_state["feedback"] = req.feedback
    approval_state["event"].set()
    return {"status": "Action approval processed."}


@app.post("/api/develop/toggle-approval")
async def toggle_approval(require: bool):
    """Live-toggle HITL approval mid-run."""
    approval_settings["require"] = require
    # If we just disabled approval and the agent is waiting for one, auto-approve it
    if not require and not approval_state["event"].is_set():
        approval_state["approved"] = True
        approval_state["feedback"] = None
        approval_state["event"].set()
    return {"status": f"Approval requirement set to {require}"}


if __name__ == "__main__":
    import uvicorn

    # To run: python main.py
    uvicorn.run(app, host="127.0.0.1", port=8000)
