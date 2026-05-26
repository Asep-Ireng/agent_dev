"""
agent_loop.py — Core LiteLLM streaming agent loop and tool result emitter.
"""

import queue
import threading
import json as _json
import re as _re
from typing import Callable

import litellm
from dev_tools import ToolRegistry
from helpers import _emit


def run_agent_loop(
    system_prompt: str,
    task_description: str,
    tool_registry: ToolRegistry,
    model: str,
    q: queue.Queue,
    abort_event: threading.Event,
    approval_callback: Callable,
    stream_callback: Callable,
    max_iter: int = 75,
    llm_kwargs: dict = {},
) -> dict:
    """
    Native litellm streaming loop that replaces Crew.kickoff().

    Uses OpenAI-compatible function calling — no stdout parsing, no monkeypatching.
    Emits typed SSE events directly onto q throughout execution.

    Returns: {"status": str, "summary": str, "usage": dict}
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_description},
    ]

    task_status = {}
    usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    tools = tool_registry.get_schemas()

    for iteration in range(max_iter):
        if abort_event.is_set():
            _emit(q, "system", {"text": "Abort signal received. Terminating...", "level": "warn"})
            return {"status": "killed", "summary": "", "usage": usage_totals}

        _emit(q, "system", {"text": f"[Step {iteration + 1}] Calling model...", "level": "info"})

        # ---- Call the LLM ----
        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
                **llm_kwargs,
            )
        except Exception as e:
            _emit(q, "system", {"text": f"LLM call failed: {str(e)}", "level": "error"})
            return {"status": "failed", "summary": str(e), "usage": usage_totals}

        # ---- Stream and accumulate the response ----
        accumulated_content = ""
        accumulated_tool_calls = {}  # index -> {id, name, arguments_str}
        finish_reason = None
        got_thinking = False

        for chunk in response:
            if abort_event.is_set():
                _emit(q, "system", {"text": "Abort signal received mid-stream.", "level": "warn"})
                return {"status": "killed", "summary": "", "usage": usage_totals}

            try:
                choice = chunk.choices[0]
                delta = choice.delta
                finish_reason = choice.finish_reason or finish_reason

                # Track usage if present
                if hasattr(chunk, "usage") and chunk.usage:
                    usage_totals["prompt_tokens"] += getattr(chunk.usage, "prompt_tokens", 0) or 0
                    usage_totals["completion_tokens"] += getattr(chunk.usage, "completion_tokens", 0) or 0
                    usage_totals["total_tokens"] += getattr(chunk.usage, "total_tokens", 0) or 0

                # Emit reasoning/thinking tokens in real-time
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    if not got_thinking:
                        _emit(q, "system", {"text": "[Thinking...]", "level": "info"})
                        got_thinking = True
                    _emit(q, "model_thinking", {"text": reasoning})

                # Accumulate text content
                if delta.content:
                    accumulated_content += delta.content

                # Accumulate tool call arguments (they stream in fragments)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "" if tc.function else "",
                                "arguments_str": "",
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["arguments_str"] += tc.function.arguments

            except (IndexError, AttributeError):
                continue

        # ---- Process the assembled response ----

        # Case 1: No tool calls — this is the final answer. Only emit final_answer, not thought.
        if not accumulated_tool_calls:
            final_text = accumulated_content.strip()
            if final_text:
                _emit(q, "final_answer", {"text": final_text})

            # Extract status from ReportTaskStatus if it was called
            status = task_status.get("status", "success")
            summary = task_status.get("summary", final_text[:500] if final_text else "")
            _emit(q, "system", {"text": f"Agent finished after {iteration + 1} step(s).", "level": "info"})
            return {"status": status, "summary": summary, "usage": usage_totals}

        # Case 2: Tool calls — emit thought if text came along with the tool call
        if accumulated_content.strip():
            _emit(q, "thought", {"text": accumulated_content.strip()})

        # Append assistant message with tool calls to history
        assistant_msg = {
            "role": "assistant",
            "content": accumulated_content or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments_str"],
                    },
                }
                for tc in accumulated_tool_calls.values()
            ],
        }
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in accumulated_tool_calls.values():
            tool_name = tc["name"]
            tool_id = tc["id"]
            args_str = tc["arguments_str"]

            # Parse args
            try:
                args = _json.loads(args_str) if args_str else {}
            except _json.JSONDecodeError:
                args = {}
                _emit(q, "system", {"text": f"Failed to parse args for {tool_name}: {args_str[:200]}", "level": "warn"})

            # Emit tool call to frontend
            _emit(q, "tool_call", {"tool": tool_name, "input": ""})
            _emit(q, "tool_input", {"input": args_str})

            # HITL: check approval if needed
            if approval_callback:
                display = f"{tool_name}\n{_json.dumps(args, indent=2)}"
                try:
                    approved, feedback = approval_callback(display)
                    if not approved:
                        reason = feedback.strip() if feedback else "No reason given."
                        tool_result = f"[SYSTEM MESSAGE - CRITICAL]\nUser rejected this tool call.\nReason: '{reason}'.\nDo NOT try this again."
                        _emit(q, "tool_result", {
                            "tool": tool_name, "cwd": "", "cmd": "",
                            "stdout": tool_result, "stderr": "", "exit_code": 1,
                            "success": False, "raw": tool_result,
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": tool_result,
                        })
                        continue
                except InterruptedError:
                    _emit(q, "system", {"text": "Aborted by user during approval.", "level": "warn"})
                    return {"status": "killed", "summary": "", "usage": usage_totals}

            # Execute tool
            if abort_event.is_set():
                return {"status": "killed", "summary": "", "usage": usage_totals}

            tool_result = tool_registry.execute(tool_name, args)

            # Capture status from ReportTaskStatusTool
            if tool_name == "report_task_status" and "[SUCCESS]" in tool_result:
                tool_obj = tool_registry.get_tool(tool_name)
                if hasattr(tool_obj, "result_holder"):
                    task_status.update(tool_obj.result_holder)

            # Build structured tool_result event for frontend
            _emit_tool_result(q, tool_name, tool_result)

            # Append tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": tool_result,
            })

    # Hit max iterations
    _emit(q, "system", {"text": f"Reached max iterations ({max_iter}). Stopping.", "level": "warn"})
    status = task_status.get("status", "partial")
    return {"status": status, "summary": task_status.get("summary", ""), "usage": usage_totals}


def _emit_tool_result(q: queue.Queue, tool_name: str, result_text: str):
    """Parse tool result string and emit a structured tool_result SSE event."""
    if "[CWD]" in result_text:
        cwd_match = _re.search(r"\[CWD\]\s*(.+?)(?:\n|\[CMD\]|$)", result_text)
        cmd_match = _re.search(r"\[CMD\]\s*(.+?)(?:\n|\[STDOUT\]|\[STDERR\]|\[EXIT\]|$)", result_text)
        stdout_match = _re.search(r"\[STDOUT\]\s*\n?(.*?)(?:\[STDERR\]|\[EXIT\]|$)", result_text, _re.DOTALL)
        stderr_match = _re.search(r"\[STDERR\]\s*\n?(.*?)(?:\[EXIT\]|$)", result_text, _re.DOTALL)
        exit_match = _re.search(r"\[EXIT\]\s*(\d+)", result_text)

        cwd = cwd_match.group(1).strip() if cwd_match else ""
        cmd = cmd_match.group(1).strip() if cmd_match else ""
        stdout = stdout_match.group(1).strip() if stdout_match else ""
        stderr = stderr_match.group(1).strip() if stderr_match else ""
        exit_code = int(exit_match.group(1)) if exit_match else None
        success = "[SUCCESS]" in result_text or exit_code == 0

        _emit(q, "tool_result", {
            "tool": "terminal",
            "cwd": cwd, "cmd": cmd,
            "stdout": stdout, "stderr": stderr,
            "exit_code": exit_code, "success": success, "raw": "",
        })
    elif "WRITE_FILE" in result_text or "File written" in result_text:
        success = "[SUCCESS]" in result_text
        _emit(q, "tool_result", {
            "tool": "write_file",
            "cwd": "", "cmd": "",
            "stdout": result_text, "stderr": "",
            "exit_code": 0 if success else 1,
            "success": success, "raw": "",
        })
    else:
        success = "[FAILED]" not in result_text and "Error" not in result_text
        _emit(q, "tool_result", {
            "tool": tool_name,
            "cwd": "", "cmd": "",
            "stdout": result_text, "stderr": "",
            "exit_code": 0 if success else 1,
            "success": success, "raw": result_text,
        })
