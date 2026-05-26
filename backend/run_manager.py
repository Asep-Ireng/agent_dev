"""
run_manager.py — Per-request run state management.
"""

import threading
import uuid
from config import _active_runs, _active_runs_lock


def _make_run_state() -> tuple[str, dict]:
    """Create a new per-request run state. Returns (run_id, state_dict)."""
    run_id = str(uuid.uuid4())
    state = {
        "abort": threading.Event(),
        "approval_event": threading.Event(),
        "approved": False,
        "feedback": None,
    }
    with _active_runs_lock:
        _active_runs[run_id] = state
    return run_id, state


def _cleanup_run(run_id: str):
    with _active_runs_lock:
        _active_runs.pop(run_id, None)


def _get_run(run_id: str | None) -> dict | None:
    """Get run state, falling back to the most recently created run if no ID given."""
    with _active_runs_lock:
        if run_id and run_id in _active_runs:
            return _active_runs[run_id]
        # Fallback for backwards compatibility (single-user local use)
        if _active_runs:
            return list(_active_runs.values())[-1]
    return None
