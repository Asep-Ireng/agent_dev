# AI Dev Studio — Project Component Map

## Backend (`backend/`)

### [main.py](backend/main.py) — Core API Server

FastAPI server with all endpoints and agent orchestration.

| Endpoint                            | Purpose                                                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `POST /api/design/chat`             | Design chat — takes user ideas/files, runs a CrewAI design agent with `UpdateSpecTool` to generate/update the spec |
| `POST /api/dev-chat`                | Dev chat — lightweight LLM call for Ask/Apply mode (no agent, just litellm)                                        |
| `GET /api/develop`                  | **Main build** — SSE stream, spawns a CrewAI dev agent that builds the app from spec                               |
| `GET /api/dev-iterate`              | **Iterate build** — SSE stream, spawns an iterate agent for targeted changes (Apply mode)                          |
| `POST /api/develop/stop`            | Kill switch — sets `abort_event` to stop the running agent                                                         |
| `POST /api/develop/approve`         | HITL — approve/reject a pending action                                                                             |
| `POST /api/develop/toggle-approval` | Live-toggle HITL mid-run (auto-approves pending if disabled)                                                       |

**Key internals:**

- `StreamCatcher` — captures CrewAI's stdout, parses ReAct patterns (`Thought:`, `Action:`, `Observation:`), and emits typed SSE events
- `approval_settings` — mutable global dict for live HITL toggling
- `abort_event` / `approval_state` — threading primitives for stop + approval flow

---

### [dev_tools.py](backend/dev_tools.py) — Development Agent Tools

All tools available to the dev and iterate agents:

| Tool                    | What it does                                                                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `TerminalExecutionTool` | Runs shell commands with real-time output streaming, approval flow, timeout (300s), and**output truncation** (5K char cap to save tokens) |
| `WriteFileTool`         | Creates/overwrites files in the workspace                                                                                                 |
| `ReadFileTool`          | Reads files with optional line range                                                                                                      |
| `ReplaceInFileTool`     | Find-and-replace exact text in a file                                                                                                     |
| `EditFileLinesTool`     | Replace a specific line range                                                                                                             |
| `InsertAtLineTool`      | Insert content before a specific line                                                                                                     |
| `ReportTaskStatusTool`  | LLM self-reports task status (`success`/`failed`/`partial`) before finishing                                                              |

---

### [design_tools.py](backend/design_tools.py) — Design Agent Tools

Single tool for the design chat agent:

| Tool             | What it does                                                                                                                                              |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `UpdateSpecTool` | Saves the updated spec + a change summary into a shared dict. The backend reads this to return both the spec and a human-readable summary of what changed |

---

## Frontend (`frontend/src/app/`)

### Components (`frontend/src/app/components/`)

Our UI has been extracted into modular components, managed by the root `page.tsx`:

| Component         | What it does                                                            |
| ----------------- | ----------------------------------------------------------------------- |
| `Sidebar.tsx`     | Provider/model selection, workspace path, HITL toggle (live-toggleable) |
| `DesignChat.tsx`  | Chat with the design agent, attach files (PDFs, images)                 |
| `SpecViewer.tsx`  | Specification preview and raw editor                                    |
| `Terminal.tsx`    | Live terminal stream, tool result cards, agent thoughts                 |
| `AgentResult.tsx` | Output from the last dev run                                            |
| `DevChat.tsx`     | Ask/Apply mode toggle, chat with LLM about the code, Proceed/Cancel     |

### [page.tsx](frontend/src/app/page.tsx) — State Container

The main page acts as the master state controller and layout provider, managing state for all child components.

**Key state:**

- `spec` — the current architecture spec (synced between design chat and spec editor)
- `agentResult` — output from the last dev run (passed as `dev_context` to iterate agent)
- `pendingApplyTask` — holds the agent's proposed plan in Apply mode until user approves
- `requireApproval` — HITL toggle, live-synced to backend via `/api/develop/toggle-approval`
- `actionLogs` — parsed SSE stream for the Terminal component### [globals.css](frontend/src/app/globals.css) — Global Styles

Custom color palette, Tailwind imports, base styling.

---

## Data Flow

```
User idea → Design Chat → UpdateSpecTool → Spec
                                              ↓
                                    "Build from Spec"
                                              ↓
                            Dev Agent (75 iter max)
                          TerminalTool, WriteFile, etc.
                                              ↓
                                         agentResult
                                              ↓
                              Dev Chat (Ask/Apply mode)
                                              ↓
                                    Iterate Agent (50 iter max)
                                    gets spec + dev_context
```
