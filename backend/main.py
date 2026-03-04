from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
from PyPDF2 import PdfReader
from crewai import Agent, Task, Crew
from fastapi.responses import StreamingResponse
from agent_tools import TerminalExecutionTool, WriteFileTool, ReadFileTool, ReplaceInFileTool, EditFileLinesTool, InsertAtLineTool
from dotenv import load_dotenv

app = FastAPI(title="AI Agent Developer Backend")

# Global event to signal the background Agent thread to abort execution
abort_event = threading.Event()

# State for HITL execution approvals
approval_state = {
    "event": threading.Event(),
    "approved": False,
    "feedback": None
}

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

# Shared AI Helper
def get_llm(model_name: str, provider: str):
    if provider == "Google (Gemini)":
        return f"gemini/{model_name}"
    return model_name

def set_keys(api_key: str, provider: str):
    if provider == "OpenAI":
        os.environ["OPENAI_API_KEY"] = api_key
    elif provider == "Google (Gemini)":
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_API_KEY"] = api_key
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")


# ==================================
# API ROUTES & MODELS
# ==================================

class DesignRequest(BaseModel):
    idea: str
    provider: str
    model: str
    api_key: str

class DevelopRequest(BaseModel):
    spec: str
    provider: str
    model: str
    api_key: str

@app.post("/api/design/chat")
async def generate_design_chat(
    idea: str = Form(...),
    spec: str = Form(""),
    provider: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(...),
    files: List[UploadFile] = File(None)
):
    try:
        set_keys(api_key, provider)
        
        # 1. Process Uploaded Files
        file_context = ""
        image_urls = []
        
        if files:
            for file in files:
                contents = await file.read()
                
                # Extract PDF text
                if file.filename.lower().endswith('.pdf'):
                    pdf_reader = PdfReader(io.BytesIO(contents))
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    file_context += f"\n--- PDF Extracted Content: {file.filename} ---\n{text}\n"
                
                # Encode Images to Base64 (Useful if model natively supports data URLs in CrewAI)
                elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    base64_image = base64.b64encode(contents).decode('utf-8')
                    mime_type = file.content_type
                    data_url = f"data:{mime_type};base64,{base64_image}"
                    image_urls.append(data_url)
                    file_context += f"\n--- Image Uploaded: {file.filename} (passed natively) ---\n"

        # 2. Build the Prompt Context
        context_prompt = f"User Request / Idea: {idea}\n\n"
        if spec:
            context_prompt += f"CURRENT SPECIFICATION (Edit this based on the user's new request):\n{spec}\n\n"
        if file_context:
            context_prompt += f"ATTACHED FILE CONTEXT:\n{file_context}\n\n"
        
        designer = Agent(
            role='Lead Product Designer',
            goal='Design and aggressively iterate on a comprehensive app technical spec based on user chat and file uploads.',
            backstory="You are a visionary Product Manager. You take rough ideas, uploaded context (like PDFs), and output pristine Markdown architecture specs.",
            verbose=True,
            allow_delegation=False,
            llm=get_llm(model, provider)
        )
        
        # CrewAI currently handles text best. For true multimodal image support through litellm 
        # inside CrewAI, you'd inject the images directly into the human message payload. 
        # For now, we inform the agent of the images, and rely on standard text reasoning.
        design_task = Task(
            description=f'Read the following constraints and current state, then output a completely rewritten, cohesive Markdown architectural spec.\n\n{context_prompt}',
            expected_output='Markdown document with the entire architecture. Do not include chatty text, only the markdown.', 
            agent=designer
        )
        
        crew = Crew(agents=[designer], tasks=[design_task])
        result = crew.kickoff()
        
        raw_output = result.raw if hasattr(result, 'raw') else str(result)
        return {"spec": raw_output}
        
    except Exception as e:
        print(f"Server Error during Design Chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dev-chat")
async def dev_chat(
    message: str = Form(...),
    spec: str = Form(""),
    workspace_path: str = Form("./workspace"),
    history: str = Form("[]"),  # JSON string of [{role, content}]
    provider: str = Form("Google (Gemini)"),
    model: str = Form("gemini-2.5-flash-preview-05-20                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   "),
    api_key: str = Form(""),
    files: List[UploadFile] = File(default=[])
):
    """Chat with the dev agent about the code it built, with optional image attachments."""
    set_keys(api_key, provider)
    
    try:
        import litellm
        import json
        
        # Parse chat history from JSON string
        chat_history = json.loads(history) if history else []
        
        # Scan the workspace for a file tree to give the agent context
        file_tree = []
        ws = os.path.abspath(workspace_path)
        if os.path.exists(ws):
            for root, dirs, files_list in os.walk(ws):
                dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '__pycache__', '.next', 'dist', 'build', '.venv', 'venv')]
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
        
        # Add chat history
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Build the current user message — may include images
        user_content = []
        user_content.append({"type": "text", "text": message})
        
        # Process uploaded images
        if files:
            for file in files:
                contents = await file.read()
                if file.filename and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                    b64 = base64.b64encode(contents).decode('utf-8')
                    mime = file.content_type or "image/png"
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}
                    })
        
        # Use multimodal format if images are attached, plain text otherwise
        if len(user_content) == 1:
            messages.append({"role": "user", "content": message})
        else:
            messages.append({"role": "user", "content": user_content})
        
        model_str = get_llm(model, provider)
        response = litellm.completion(model=model_str, messages=messages)
        
        reply = response.choices[0].message.content
        return {"reply": reply}
        
    except Exception as e:
        print(f"Server Error during Dev Chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

import json as _json
import re as _re

def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and naked color codes from CrewAI/langchain output."""
    text = _re.sub(r'\x1b\[[0-9;]*[mGKF]', '', text)
    text = _re.sub(r'\[\d+m', '', text)
    return text.strip()

def _emit(q: queue.Queue, event_type: str, payload: dict):
    """Helper to push a typed SSE event onto the queue."""
    q.put(f"event: {event_type}\ndata: {_json.dumps(payload)}\n\n")

@app.get("/api/develop")
async def generate_code_stream(
    spec: str,
    provider: str,
    model: str,
    api_key: str,
    workspace_path: str = "./workspace",
    require_approval: str = "false"
):
    set_keys(api_key, provider)
    
    # Reset the abort event before starting a new run
    abort_event.clear()
    
    q = queue.Queue()

    class StreamCatcher:
        """Captures CrewAI stdout, parses ReAct patterns, and emits typed SSE events."""
        def __init__(self):
            self.buffer = ""
            
        def write(self, text):
            if not text or not text.strip():
                return
            
            clean = _strip_ansi(text)
            if not clean:
                return
            
            # --- Detect CrewAI ReAct patterns ---
            
            # Agent start / delegation header
            if clean.startswith("Agent:") or clean.startswith("## Agent:"):
                _emit(q, "system", {"text": clean, "level": "info"})
                return
            
            # Task header
            if clean.startswith("Task:") or clean.startswith("## Task:"):
                _emit(q, "system", {"text": clean, "level": "info"})
                return
            
            # Agent thinking / reasoning
            if clean.startswith("Thought:") or clean.startswith("> Thinking:"):
                thought_text = clean.split(":", 1)[1].strip() if ":" in clean else clean
                _emit(q, "thought", {"text": thought_text})
                return

            # Tool call detection
            if clean.startswith("Action:"):
                tool_name = clean.split(":", 1)[1].strip() if ":" in clean else clean
                _emit(q, "tool_call", {"tool": tool_name, "input": ""})
                return
            
            if clean.startswith("Action Input:"):
                action_input = clean.split(":", 1)[1].strip() if ":" in clean else clean
                _emit(q, "tool_input", {"input": action_input})
                return

            # Tool result / observation — parse structured markers from our tools
            if clean.startswith("Observation:") or "Tool" in clean and "executed with result" in clean:
                self._emit_tool_result(clean)
                return
            
            # Final answer
            if clean.startswith("Final Answer:"):
                answer_text = clean.split(":", 1)[1].strip() if ":" in clean else clean
                _emit(q, "final_answer", {"text": answer_text})
                return
            
            # System messages from our own code
            if clean.startswith("[SYSTEM]"):
                level = "info"
                if "[WARN]" in clean:
                    level = "warn"
                elif "[ERROR]" in clean:
                    level = "error"
                _emit(q, "system", {"text": clean, "level": level})
                return
            
            # Everything else — send as raw log
            _emit(q, "log", {"text": clean})

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
                cwd_match = _re.search(r'\[CWD\]\s*(.+?)(?:\n|\[CMD\]|$)', parts)
                cmd_match = _re.search(r'\[CMD\]\s*(.+?)(?:\n|\[STDOUT\]|\[STDERR\]|\[EXIT\]|$)', parts)
                stdout_match = _re.search(r'\[STDOUT\]\s*\n?(.*?)(?:\[STDERR\]|\[EXIT\]|$)', parts, _re.DOTALL)
                stderr_match = _re.search(r'\[STDERR\]\s*\n?(.*?)(?:\[EXIT\]|$)', parts, _re.DOTALL)
                exit_match = _re.search(r'\[EXIT\]\s*(\d+)', parts)
                
                if cwd_match: cwd = cwd_match.group(1).strip()
                if cmd_match: cmd = cmd_match.group(1).strip()
                if stdout_match: stdout = stdout_match.group(1).strip()
                if stderr_match: stderr = stderr_match.group(1).strip()
                if exit_match: exit_code = int(exit_match.group(1))
                
                success = "[SUCCESS]" in result_text or exit_code == 0
                
                _emit(q, "tool_result", {
                    "tool": "terminal",
                    "cwd": cwd,
                    "cmd": cmd,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                    "success": success,
                    "raw": ""
                })
            elif "WRITE_FILE" in result_text or "File written" in result_text:
                success = "[SUCCESS]" in result_text
                _emit(q, "tool_result", {
                    "tool": "write_file",
                    "cwd": "",
                    "cmd": "",
                    "stdout": result_text,
                    "stderr": "",
                    "exit_code": 0 if success else 1,
                    "success": success,
                    "raw": ""
                })
            else:
                # Generic tool result
                success = "[FAILED]" not in result_text and "Error" not in result_text
                _emit(q, "tool_result", {
                    "tool": "unknown",
                    "cwd": "",
                    "cmd": "",
                    "stdout": result_text,
                    "stderr": "",
                    "exit_code": 0 if success else 1,
                    "success": success,
                    "raw": result_text
                })
                
        def flush(self):
            pass

    def run_crew():
        killed = False
        old_stdout = sys.stdout
        sys.stdout = StreamCatcher()
        try:
            _emit(q, "system", {"text": "Initializing Developer Agent...", "level": "info"})
            
            def approval_callback(command: str) -> tuple[bool, str | None]:
                # Notify frontend that an action needs approval
                q.put(f"event: action_required\ndata: {_json.dumps({'command': command})}\n\n")
                
                # Clear the event and wait for the user to hit the approve/reject endpoint
                approval_state["event"].clear()
                
                # Wait loop so we can still bail quickly if STOP is hit
                while not approval_state["event"].is_set() and not abort_event.is_set():
                    approval_state["event"].wait(0.5)
                
                if abort_event.is_set():
                    raise InterruptedError("User triggered manual stop while waiting for approval.")
                    
                return (approval_state["approved"], approval_state.get("feedback"))

            def stream_callback(event_type, data):
                """Stream subprocess output to frontend in real-time."""
                if event_type == "cmd_start":
                    _emit(q, "cmd_start", data)
                elif event_type == "cmd_end":
                    _emit(q, "cmd_end", data)
                elif event_type in ("stdout", "stderr"):
                    _emit(q, "cmd_output", {"stream": event_type, "line": data})
            
            terminal_tool = TerminalExecutionTool(
                workspace_path=workspace_path,
                require_approval=(require_approval.lower() == "true"),
                approval_callback=approval_callback,
                stream_callback=stream_callback
            )
            
            write_file_tool = WriteFileTool(
                workspace_path=workspace_path,
                require_approval=(require_approval.lower() == "true"),
                approval_callback=approval_callback
            )
            
            read_file_tool = ReadFileTool(workspace_path=workspace_path)
            
            replace_in_file_tool = ReplaceInFileTool(
                workspace_path=workspace_path,
                require_approval=(require_approval.lower() == "true"),
                approval_callback=approval_callback
            )
            
            edit_file_lines_tool = EditFileLinesTool(
                workspace_path=workspace_path,
                require_approval=(require_approval.lower() == "true"),
                approval_callback=approval_callback
            )
            
            insert_at_line_tool = InsertAtLineTool(
                workspace_path=workspace_path,
                require_approval=(require_approval.lower() == "true"),
                approval_callback=approval_callback
            )
            
            def check_abort(*args, **kwargs):
                if abort_event.is_set():
                    _emit(q, "system", {"text": "Abort signal received. Terminating...", "level": "warn"})
                    raise InterruptedError("User triggered manual stop.")

            developer = Agent(
                role='Autonomous Principal Developer',
                goal='Build and execute the provided application spec directly in the filesystem.',
                backstory="You are a 10x systems engineer who builds applications entirely using the terminal. IMPORTANT: Before doing ANYTHING else, you MUST create a dedicated project folder inside the workspace (e.g. 'mkdir my-app-name') and do ALL your work inside that folder. This keeps the workspace clean when multiple projects exist. When scaffolding projects with npx, npm, or any CLI tools, ALWAYS use non-interactive flags (e.g. 'npx -y create-next-app@latest ./my-app --yes --typescript --eslint --tailwind --app --src-dir --no-import-alias', 'npm init -y', 'npx -y create-vite@latest ./my-app -- --template react-ts'). NEVER run interactive prompts — they will hang and timeout. You use your Execute Terminal Command tool to create directories, install dependencies, and run scripts. You ALWAYS use your Write File tool to save NEW source code into files. Do NOT use echo or cat to write long blocks of code into files, use Write File instead. When you need to EDIT an existing file, ALWAYS use Read File first to see the current content and line numbers. For targeted edits, use Edit File Lines (to replace a specific line range) or Insert At Line (to add code at a specific position). Use Replace In File if you have a unique text snippet to match. Never rewrite a whole file just to change a few lines.",
                verbose=True,
                allow_delegation=False,
                llm=get_llm(model, provider),
                tools=[terminal_tool, write_file_tool, read_file_tool, replace_in_file_tool, edit_file_lines_tool, insert_at_line_tool],
                step_callback=check_abort
            )
            
            dev_task = Task(
                description=f'Read this approved spec. FIRST, create a dedicated project folder inside the workspace directory (name it based on the app name from the spec). Then build everything inside that folder. Execute terminal commands to build the file structure and write the code locally:\n\n{spec}',
                expected_output='A completely built and installed application within the workspace.', 
                agent=developer
            )
            
            crew = Crew(agents=[developer], tasks=[dev_task])
            crew_result = crew.kickoff()
            
            # Emit the final crew result as a dedicated event for the result panel
            raw_result = crew_result.raw if hasattr(crew_result, 'raw') else str(crew_result)
            if raw_result and raw_result.strip():
                _emit(q, "result", {"text": raw_result})
        except InterruptedError as e:
            killed = True
            _emit(q, "system", {"text": f"Process stopped: {str(e)}", "level": "warn"})
        except Exception as e:
            _emit(q, "system", {"text": f"Build failure: {str(e)}", "level": "error"})
        finally:
            sys.stdout = old_stdout
            q.put(f"event: done\ndata: {_json.dumps({'killed': killed})}\n\n")

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

if __name__ == "__main__":
    import uvicorn
    # To run: python main.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
