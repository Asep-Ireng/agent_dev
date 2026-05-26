"""
routers/control.py — /api/develop/stop, /api/develop/approve, /api/develop/toggle-approval endpoints.
"""

from fastapi import APIRouter
from config import ApproveRequest, approval_settings
from run_manager import _get_run

router = APIRouter()


@router.post("/api/develop/stop")
async def stop_development(run_id: str | None = None):
    """Kill switch — sets abort_event for the specified (or latest) run."""
    run = _get_run(run_id)
    if run:
        run["abort"].set()
    return {"status": "Abort signal sent."}


@router.post("/api/develop/approve")
async def approve_action(req: ApproveRequest):
    run = _get_run(req.run_id)
    if run:
        run["approved"] = req.approved
        run["feedback"] = req.feedback
        run["approval_event"].set()
    return {"status": "Action approval processed."}


@router.post("/api/develop/toggle-approval")
async def toggle_approval(require: bool, run_id: str | None = None):
    """Live-toggle HITL approval mid-run."""
    approval_settings["require"] = require
    # If we just disabled approval and the agent is waiting for one, auto-approve it
    if not require:
        run = _get_run(run_id)
        if run and not run["approval_event"].is_set():
            run["approved"] = True
            run["feedback"] = None
            run["approval_event"].set()
    return {"status": f"Approval requirement set to {require}"}
