# Agentic Dev Studio — Backend Component Map

This is the backend service for the **Agentic Dev Studio**, constructed as a Python application powered by FastAPI and LiteLLM.

## Directory Structure

```
backend/
├── main.py                # Thin entry point: FastAPI app wiring + uvicorn guard
├── config.py              # Global state, runtime_settings, BASE_WORKSPACE_DIR, Pydantic models
├── helpers.py             # Pure utility functions (validation, prompt building, SSE emit)
├── agent_loop.py          # LiteLLM streaming agent loop engine + tool result emitter
├── run_manager.py         # Per-request run state management (_active_runs, make/cleanup/get)
├── routers/               # One file per endpoint group
│   ├── settings.py        # GET/POST /api/settings, GET /api/workspace/diff
│   ├── design.py          # POST /api/design/chat
│   ├── develop.py         # POST /api/develop (SSE)
│   ├── iterate.py         # POST /api/dev-iterate (SSE)
│   ├── dev_chat.py        # POST /api/dev-chat
│   └── control.py         # /api/develop/stop, /approve, /toggle-approval
├── dev_tools.py           # Tools for the Development Agent
├── design_tools.py        # Tools for the Design Agent
├── config/
│   └── agents.yaml        # YAML configuration for agent personas
└── tests/                 # Isolated testing & scratch utility scripts
```

---

## Core Service Files

### 1. `main.py` (App Entry Point)
A thin wiring shell (~40 lines). Instantiates the FastAPI app, configures CORS middleware, and registers all routers via `app.include_router()`.

### 2. `config.py` (Global State)
Single source of truth for mutable shared state:
*   `runtime_settings` — provider, model, thinking level (loaded from `.env`, updatable via API)
*   `approval_settings` — live-toggleable HITL flag
*   `BASE_WORKSPACE_DIR` — sandboxed workspace root
*   `_active_runs` / `_active_runs_lock` — per-run state registry
*   All Pydantic request models (`DevelopRequest`, `IterateRequest`, `ApproveRequest`, etc.)

### 3. `helpers.py` (Utility Functions)
Pure functions with no side effects (except `set_keys_from_env`):
*   Provider/model resolution (`get_current_provider`, `get_current_model`, `get_litellm_model`)
*   `set_keys_from_env()` — applies `.env` API keys to the environment
*   `validate_workspace_path()` / `validate_chat_history()` — input validation
*   `build_system_prompt()` — constructs agent system prompts from `agents.yaml` config
*   `_emit()` — pushes typed SSE events onto a queue

### 4. `agent_loop.py` (Agent Engine)
The core LiteLLM streaming loop that replaces the old CrewAI `kickoff()` approach:
*   `run_agent_loop()` — iterative tool-calling loop with abort/approval support, streaming token accumulation, and usage tracking
*   `_emit_tool_result()` — parses tool output strings and emits structured `tool_result` SSE events

### 5. `run_manager.py` (Run State)
Manages the per-request lifecycle registry:
*   `_make_run_state()` — creates a new run entry with abort/approval events
*   `_cleanup_run()` — removes a completed run
*   `_get_run()` — retrieves a run by ID (with single-user fallback)

### 6. `routers/` (Endpoint Handlers)
Each file contains an `APIRouter` with focused responsibilities:
*   `settings.py` — runtime config read/write and git diff
*   `design.py` — one-shot LLM call for spec generation via `UpdateSpecTool`
*   `develop.py` — full autonomous build agent (SSE streamed, 75 max iterations)
*   `iterate.py` — targeted patch agent for existing codebases (SSE streamed, 50 max iterations)
*   `dev_chat.py` — conversational Q&A about the built project, supports image attachments
*   `control.py` — kill switch, HITL approval, and live approval toggling

### 7. `dev_tools.py` (Development Toolkit)
Provides custom physical operation tools to the developer agent:
*   `TerminalExecutionTool`: Runs bash commands on the local machine with real-time output capture, line limits, and manual HITL approvals.
*   `WriteFileTool` / `ReadFileTool`: Operations for reading/writing full target files inside the workspace.
*   `ReplaceInFileTool` / `EditFileLinesTool` / `InsertAtLineTool`: Precise text-patching operations.
*   `ReportTaskStatusTool`: Reporting step status (`success`, `failed`, or `partial`) back to the parent workspace database.

### 8. `design_tools.py` (Design Toolkit)
Contains `UpdateSpecTool` which is utilized by the Lead Designer agent to programmatically rewrite/modify markdown target design documents.

### 9. `config/agents.yaml`
Centralizes backstories, roles, and goal models for the `Lead Designer`, `Lead Developer`, and `Iterative Developer` agent personas.

---

## Testing & Scratch utilities (`tests/`)

We maintain a suite of modular testing scripts to troubleshoot LLM completions, mock streaming, and patch agent workflows:
*   `test_litellm_stream.py`: Exercises raw stream completion loops using LiteLLM.
*   `test_llm.py`: Quick verification script checking model connection latency and API key health.
*   `test_stream_true.py`: Test specifically for testing dynamic text streaming when `stream=True` is enabled.

