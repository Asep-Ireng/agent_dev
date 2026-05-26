"""
routers/develop.py — POST /api/develop SSE endpoint.
"""

import os
import queue
import asyncio
import threading
import json as _json
import yaml

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from config import runtime_settings, approval_settings, BASE_WORKSPACE_DIR, DevelopRequest
from helpers import (
    get_current_provider,
    get_current_model,
    get_litellm_model,
    set_keys_from_env,
    validate_workspace_path,
    build_system_prompt,
    _emit,
)
from agent_loop import run_agent_loop
from run_manager import _make_run_state, _cleanup_run
from dev_tools import create_dev_tool_registry

router = APIRouter()

_AGENTS_YAML = os.path.join(os.path.dirname(__file__), "..", "config", "agents.yaml")


@router.post("/api/develop")
async def generate_code_stream(req: DevelopRequest):
    set_keys_from_env()
    provider = get_current_provider()
    model = get_current_model()
    model_str = get_litellm_model(model, provider)
    workspace_path = validate_workspace_path(req.workspace_path)
    require_approval = req.require_approval
    spec = req.spec

    approval_settings["require"] = require_approval

    q = queue.Queue()
    run_id, run_state = _make_run_state()
    abort_event = run_state["abort"]

    def run_develop():
        killed = False
        errored = False
        task_status = {}
        final_status = "failed"
        metrics = {}

        try:
            _emit(q, "system", {"text": "Initializing Developer Agent...", "level": "info"})

            def raw_approval_callback(command: str) -> tuple[bool, str | None]:
                q.put(
                    f"event: action_required\ndata: {_json.dumps({'command': command, 'run_id': run_id})}\n\n"
                )
                run_state["approval_event"].clear()
                while not run_state["approval_event"].is_set() and not abort_event.is_set():
                    run_state["approval_event"].wait(0.5)
                if abort_event.is_set():
                    raise InterruptedError("User triggered manual stop while waiting for approval.")
                return (run_state["approved"], run_state.get("feedback"))

            def approval_callback(command: str) -> tuple[bool, str | None]:
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

            with open(_AGENTS_YAML, "r", encoding="utf-8") as f:
                agents_config = yaml.safe_load(f)

            system_prompt = build_system_prompt(
                agents_config["developer"],
                workspace_path,
                extra_context=(
                    "\nIMPORTANT: Before doing ANYTHING else, create a dedicated project folder inside "
                    "the workspace directory (name it based on the app name from the spec) and do ALL your work inside that folder."
                ),
            )

            thinking_level = runtime_settings.get("thinking_level", "none")
            llm_kwargs = {}
            if provider == "Google (Gemini)" and thinking_level != "none" and "gemini" in model.lower():
                llm_kwargs["reasoning_effort"] = thinking_level

            registry = create_dev_tool_registry(
                workspace_path, require_approval, approval_callback, stream_callback, task_status
            )

            result = run_agent_loop(
                system_prompt=system_prompt,
                task_description=spec,
                tool_registry=registry,
                model=model_str,
                q=q,
                abort_event=abort_event,
                approval_callback=approval_callback if require_approval else None,
                stream_callback=stream_callback,
                max_iter=75,
                llm_kwargs=llm_kwargs,
            )

            if result["status"] == "killed":
                killed = True
            elif result["status"] == "failed":
                errored = True

            if result.get("summary"):
                _emit(q, "result", {"text": result["summary"]})

            final_status = result["status"]
            metrics = result["usage"]

        except InterruptedError as e:
            killed = True
            _emit(q, "system", {"text": f"Process stopped: {str(e)}", "level": "warn"})
            final_status = "killed"
            metrics = {}
        except Exception as e:
            errored = True
            _emit(q, "system", {"text": f"Build failure: {str(e)}", "level": "error"})
            final_status = "failed"
            metrics = {}
        finally:
            _cleanup_run(run_id)
            q.put(
                f"event: done\ndata: {_json.dumps({'killed': killed, 'error': errored, 'status': final_status, 'status_summary': task_status.get('summary', ''), 'usage': metrics, 'run_id': run_id})}\n\n"
            )

    threading.Thread(target=run_develop).start()

    async def event_generator():
        # Emit run_id immediately so frontend can use it for stop/approve
        yield f"event: run_start\ndata: {_json.dumps({'run_id': run_id})}\n\n"
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
