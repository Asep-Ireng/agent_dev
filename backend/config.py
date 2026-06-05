"""
config.py — Global state, runtime configuration, and Pydantic request models.
"""

import os
import threading
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from root .env (single source of truth)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ==================================
# GLOBAL STATE
# ==================================

# Per-request run state — keyed by run_id (UUID)
# Each entry: {"abort": threading.Event, "approval_event": threading.Event, "approved": bool, "feedback": str|None}
_active_runs: dict = {}
_active_runs_lock = threading.Lock()

# Live-toggleable approval setting (mutable dict so tools can see changes mid-run)
approval_settings = {"require": False}

# Runtime settings (loaded from .env, modifiable via API)
runtime_settings = {
    "provider": os.getenv("DEFAULT_PROVIDER", "Google (Gemini)"),
    "google_model": os.getenv("GOOGLE_MODEL", "gemini-3.5-flash"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-5.5"),
    "thinking_level": os.getenv("THINKING_LEVEL", "none"),
}

# Base workspace directory — all workspace_path values must resolve inside this
BASE_WORKSPACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "workspace")
)
os.makedirs(BASE_WORKSPACE_DIR, exist_ok=True)


# ==================================
# PYDANTIC REQUEST MODELS
# ==================================


class ApproveRequest(BaseModel):
    approved: bool
    feedback: str | None = None
    run_id: str | None = None


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
