"""
main.py — FastAPI application entry point.

Wires together all routers and middleware. All business logic lives in:
  config.py       — global state, runtime settings, Pydantic models
  helpers.py      — utility functions (validation, prompt building, SSE emit)
  agent_loop.py   — LiteLLM streaming agent loop engine
  run_manager.py  — per-request run state management
  routers/        — one file per endpoint group
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helpers import set_keys_from_env
from routers import settings, design, dev_chat, develop, iterate, control

app = FastAPI(title="AI Agent Developer Backend")

# Allow requests from our Next.js frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(settings.router)
app.include_router(design.router)
app.include_router(dev_chat.router)
app.include_router(develop.router)
app.include_router(iterate.router)
app.include_router(control.router)

# Set API keys on startup
set_keys_from_env()

if __name__ == "__main__":
    import uvicorn

    # To run: python main.py
    uvicorn.run(app, host="127.0.0.1", port=8000)
