# AI Dev Studio — Project Component Map

## Backend (`backend/`)

### Architecture Overview

The backend is a modular FastAPI application using **LiteLLM** for model-agnostic streaming completions with OpenAI-compatible function calling. Agent orchestration runs through a native streaming loop — no external agent frameworks.

```
backend/
├── main.py                # Thin entry point: FastAPI app wiring + uvicorn guard
├── config.py              # Global state, runtime_settings, BASE_WORKSPACE_DIR, Pydantic models
├── helpers.py             # Pure utility functions (validation, prompt building, SSE emit)
├── agent_loop.py          # LiteLLM streaming agent loop engine + tool result emitter
├── run_manager.py         # Per-request run state management (_active_runs, make/cleanup/get)
├── syntax_guard.py        # Content validation engine (Python/JSON AST, size cap, failure budget)
├── routers/               # One file per endpoint group
│   ├── settings.py        # GET/POST /api/settings, GET /api/workspace/diff
│   ├── design.py          # POST /api/design/chat
│   ├── develop.py         # POST /api/develop (SSE)
│   ├── iterate.py         # POST /api/dev-iterate (SSE)
│   ├── dev_chat.py        # POST /api/dev-chat
│   └── control.py         # /api/develop/stop, /approve, /toggle-approval
├── dev_tools.py           # Tools for the Development Agent (safety-hardened)
├── design_tools.py        # Tools for the Design Agent
└── config/
    └── agents.yaml        # YAML configuration for agent personas
```

---

### API Endpoints

| Endpoint                            | Method | Router          | Purpose                                                                                          |
| ----------------------------------- | ------ | --------------- | ------------------------------------------------------------------------------------------------ |
| `POST /api/design/chat`             | POST   | `design.py`     | Design chat — single-turn LLM call with `UpdateSpecTool` to generate/update the spec             |
| `POST /api/dev-chat`                | POST   | `dev_chat.py`   | Dev chat — conversational Q&A with `ReadFileTool` access (Ask mode) and image attachments        |
| `POST /api/develop`                 | POST   | `develop.py`    | **Main build** — SSE stream, spawns a LiteLLM agent loop that builds the app from spec           |
| `POST /api/dev-iterate`             | POST   | `iterate.py`    | **Iterate build** — SSE stream, spawns an iterate agent for targeted changes (Apply mode)        |
| `POST /api/develop/stop`            | POST   | `control.py`    | Kill switch — sets the per-run `abort_event` to stop the running agent                           |
| `POST /api/develop/approve`         | POST   | `control.py`    | HITL — approve/reject a pending terminal command                                                 |
| `POST /api/develop/toggle-approval` | POST   | `control.py`    | Live-toggle HITL mid-run (auto-approves pending if disabled)                                     |
| `GET /api/settings`                 | GET    | `settings.py`   | Read runtime config (provider, model, thinking level)                                            |
| `POST /api/settings`                | POST   | `settings.py`   | Update runtime config                                                                            |
| `GET /api/workspace/diff`           | GET    | `settings.py`   | Run `git diff --relative` on the workspace and return the patch                                  |

---

### Core Modules

| Module             | Responsibility                                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `main.py`          | Thin wiring shell (~45 lines). Instantiates FastAPI, configures CORS, registers all routers                        |
| `config.py`        | Global state: `runtime_settings`, `approval_settings`, `BASE_WORKSPACE_DIR`, `_active_runs`, all Pydantic models   |
| `helpers.py`       | Pure utilities: provider/model resolution, input validation, `build_system_prompt()`, `_emit()` SSE helper         |
| `agent_loop.py`    | `run_agent_loop()` — iterative LiteLLM streaming loop with abort/approval, tool dispatch, and usage tracking       |
| `run_manager.py`   | Per-request lifecycle: `_make_run_state()`, `_cleanup_run()`, `_get_run()` with single-user fallback               |
| `syntax_guard.py`  | Validation engine: `ast.parse` for `.py`, `json.loads` for `.json`, 2 MB size cap, 3-strike failure budget per run |

---

### [dev_tools.py](backend/dev_tools.py) — Development Agent Tools (Safety-Hardened)

All tools available to the dev and iterate agents:

| Tool                         | What it does                                                                                                                                              |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TerminalExecutionTool`      | Runs shell commands with real-time output streaming, HITL approval flow, timeout (300s), **command blocklist**, and output truncation (5K char cap)        |
| `WriteFileTool`              | Creates/overwrites files in the workspace with syntax + size validation                                                                                   |
| `ReadFileTool`               | Reads files with optional line range                                                                                                                      |
| `ReplaceInFileTool`          | Find-and-replace exact text in a file with post-edit validation                                                                                           |
| `EditFileLinesTool`          | Replace a specific line range with validation                                                                                                             |
| `InsertAtLineTool`           | Insert content before a specific line with validation                                                                                                     |
| `BatchReplaceFileContentTool`| **Transactional** multi-chunk replacement — anchors validated before edit, applied bottom-to-top, atomic rollback on any failure                           |
| `ReportTaskStatusTool`       | LLM self-reports task status (`success`/`failed`/`partial`) before finishing                                                                              |

**Safety features:** Command blocklist (12 regex patterns), per-file thread locks, AST syntax validation on all write paths, 2 MB size cap, 3-consecutive-failure budget per run.

---

### [design_tools.py](backend/design_tools.py) — Design Agent Tools

Single tool for the design chat agent:

| Tool             | What it does                                                                                                                                              |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `UpdateSpecTool` | Saves the updated spec + a change summary into a shared dict. The backend reads this to return both the spec and a human-readable summary of what changed |

---

## Frontend (`frontend/src/app/`)

Built with **Next.js**, **React**, **Tailwind CSS**, and **Geist Fonts**. An industrial-themed control cockpit for designing, building, and debugging autonomous projects.

### Components (`frontend/src/app/components/`)

All UI modules are managed by the root `page.tsx`:

| Component           | What it does                                                                                             |
| ------------------- | -------------------------------------------------------------------------------------------------------- |
| `Sidebar.tsx`       | Provider/model selection, workspace path, Open Codebase shortcut, HITL toggle (live-toggleable)          |
| `DesignChat.tsx`    | Chat with the design agent, attach files (PDFs, images), clipboard paste support                         |
| `SpecViewer.tsx`    | Specification preview (rendered markdown) and raw editor toggle                                          |
| `Terminal.tsx`      | Live terminal stream, tool result cards (collapsible), agent thoughts, scroll-lock + resume auto-scroll  |
| `AgentResult.tsx`   | Output summary from the last dev run                                                                     |
| `DevChat.tsx`       | Ask/Apply mode toggle, chat with LLM about the code, Proceed/Cancel, inline code diff review drawer     |
| `ModelPicker.tsx`   | Glassmorphic inline model selector with segmented provider toggle (Gemini/OpenAI)                        |
| `ThinkingPanel.tsx` | Extended thinking token stream viewer for models with reasoning capabilities                             |

### [page.tsx](frontend/src/app/page.tsx) — State Container

The main page acts as the master state controller and layout provider, managing state for all child components.

**Key state:**

- `spec` — the current architecture spec (synced between design chat and spec editor)
- `agentResult` — output from the last dev run (passed as `dev_context` to iterate agent)
- `pendingApplyTask` — holds the agent's proposed plan in Apply mode until user approves
- `requireApproval` — HITL toggle, live-synced to backend via `/api/develop/toggle-approval`
- `actionLogs` — parsed SSE stream for the Terminal component
- `totalTokens` — accumulated prompt/completion/total token usage across all endpoints

### [types.ts](frontend/src/app/types.ts) — Type Declarations

`LogEntry` union type covering all SSE event shapes: `thought`, `model_thinking`, `tool_call`, `tool_input`, `tool_result`, `final_answer`, `system`, `log`, `cmd_start`, `cmd_output`, `cmd_end`.

### [globals.css](frontend/src/app/globals.css) — Global Styles

Industrial design token catalog: Slate Matte Black (`#0F0F11`), Crimson Red (`#E51937`), Carbon Gray (`#1F1F23`). Blueprint grid pattern, industrial borders, and custom scrollbar styling.

---

## Data Flow

```
User idea → Design Chat → UpdateSpecTool → Spec
                                              ↓
                                    "Build from Spec"
                                              ↓
                            Dev Agent (LiteLLM, 75 iter max)
                          TerminalTool, WriteFile, BatchReplace, etc.
                                              ↓
                                         agentResult
                                              ↓
                              Dev Chat (Ask/Apply mode)
                                              ↓
                                    Iterate Agent (50 iter max)
                                    gets spec + dev_context
```

**Alternate entry:** `📂 Open Codebase` in the sidebar bypasses Design Chat entirely — connects directly to Dev Chat for existing projects.
