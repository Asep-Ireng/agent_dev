"""
helpers.py — Pure utility functions: provider resolution, validation, prompt building, and SSE emit.
"""

import os
import queue
import json as _json
from fastapi import HTTPException
from config import runtime_settings, BASE_WORKSPACE_DIR


# ==================================
# PROVIDER / MODEL HELPERS
# ==================================


def get_current_provider() -> str:
    return runtime_settings["provider"]


def get_current_model() -> str:
    provider = get_current_provider()
    if provider == "OpenAI":
        return runtime_settings["openai_model"]
    return runtime_settings["google_model"]


def get_litellm_model(model_name: str, provider: str) -> str:
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


# ==================================
# VALIDATION HELPERS
# ==================================


def validate_workspace_path(workspace_path: str) -> str:
    """Validate and normalize workspace_path. Returns absolute path or raises HTTPException."""
    resolved = os.path.abspath(workspace_path)
    base_with_sep = BASE_WORKSPACE_DIR + os.sep
    if resolved != BASE_WORKSPACE_DIR and not resolved.startswith(base_with_sep):
        raise HTTPException(status_code=400, detail="Invalid workspace path.")
    return resolved


def validate_chat_history(history_json: str) -> list:
    """Parse and validate chat history JSON. Returns list of validated messages."""
    MAX_CONTENT_LENGTH = 4000
    ALLOWED_ROLES = {"user", "assistant"}

    if not history_json:
        return []

    try:
        parsed = _json.loads(history_json)
    except _json.JSONDecodeError:
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


# ==================================
# PROMPT BUILDER
# ==================================


def build_system_prompt(agent_config: dict, workspace_path: str, extra_context: str = "") -> str:
    """Build a system prompt from agents.yaml config fields."""
    return (
        f"You are a {agent_config['role']}.\n\n"
        f"Your goal: {agent_config['goal']}\n\n"
        f"Background: {agent_config['backstory']}\n\n"
        f"Workspace directory: {workspace_path}\n"
        f"{extra_context}\n"
        "When you have completed the task, provide your final summary as a plain text response (do not call any more tools). "
        "Be specific about what files were created or modified."
    )


# ==================================
# SSE EMIT HELPER
# ==================================


def _emit(q: queue.Queue, event_type: str, payload: dict):
    """Helper to push a typed SSE event onto the queue."""
    q.put(f"event: {event_type}\ndata: {_json.dumps(payload)}\n\n")
