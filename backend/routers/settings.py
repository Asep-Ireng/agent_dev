"""
routers/settings.py — GET/POST /api/settings and GET /api/workspace/diff endpoints.
"""

import subprocess
from fastapi import APIRouter
from fastapi.exceptions import HTTPException

from config import runtime_settings, SettingsUpdate, BASE_WORKSPACE_DIR
from helpers import (
    get_current_provider,
    get_current_model,
    set_keys_from_env,
    validate_workspace_path,
)

router = APIRouter()


@router.get("/api/settings")
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


@router.post("/api/settings")
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


@router.get("/api/workspace/diff")
async def get_workspace_diff(workspace_path: str = BASE_WORKSPACE_DIR):
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
