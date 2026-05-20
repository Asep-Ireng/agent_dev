# Agentic Dev Studio — Backend Component Map

This is the backend service for the **Agentic Dev Studio**, constructed as a Python application powered by FastAPI and CrewAI.

## Directory Structure

```
backend/
├── main.py                # Core FastAPI app & Agent Orchestration
├── dev_tools.py           # Tools for the Development Agent
├── design_tools.py        # Tools for the Design Agent
├── config/
│   └── agents.yaml        # YAML configuration for agent personas
└── tests/                 # Isolated testing & scratch utility scripts
```

---

## Core Service Files

### 1. `main.py` (Core API Gateway)
Acts as the central API gateway and agent coordinator. Sets up endpoints and orchestrates design/development workflows:
*   **Design Endpoint (`/api/design/chat`)**: Runs an interactive chat crew that reads user descriptions/specifications and outputs/updates the architectural markdown specifications.
*   **Build Endpoint (`/api/develop`)**: Spawns the main autonomous developer agent who receives the specification and writes/modifies files. Streams telemetry using Server-Sent Events (SSE).
*   **Apply Endpoint (`/api/dev-iterate`)**: Spawns an iterative development agent to run specific instructions on top of existing workspace code.
*   **Interactive Control Endpoints (`/api/develop/stop`, `/api/develop/approve`, `/api/develop/toggle-approval`)**: Managing the execution lifecycle, handling Human-in-the-Loop (HITL) approval states, and toggling runtime triggers.

### 2. `dev_tools.py` (Development Toolkit)
Provides custom physical operation tools to the developer agent:
*   `TerminalExecutionTool`: Runs bash commands on the local machine with real-time output capture, line limits, and manual HITL approvals.
*   `WriteFileTool` / `ReadFileTool`: Operations for reading/writing full target files inside the workspace.
*   `ReplaceInFileTool` / `EditFileLinesTool` / `InsertAtLineTool`: Precise text-patching operations.
*   `ReportTaskStatusTool`: Reporting step status (`success`, `failed`, or `partial`) back to the parent workspace database.

### 3. `design_tools.py` (Design Toolkit)
Contains `UpdateSpecTool` which is utilized by the Lead Designer agent to programmatically rewrite/modify markdown target design documents.

### 4. `config/agents.yaml`
Centralizes backstories, roles, and goal models for both the `Lead Designer` and `Lead Developer` CrewAI agents.

---

## Testing & Scratch utilities (`tests/`)

We maintain a suite of modular testing scripts to troubleshoot LLM completions, mock streaming, and patch agent workflows:
*   `check_stream_type.py`: Script validating structural typing of CrewAI streaming results (e.g. `CrewStreamingOutput`).
*   `test_agent.py`: Verifies clean local loading of the main development agent crew.
*   `test_callback.py`: Tests the execution callbacks triggered by CrewAI agent actions.
*   `test_callback_llm.py`: Tests callbacks specific to model inference cycles.
*   `test_crew_stream_debug.py`: Debugging stream capture hooks inside the SSE loop.
*   `test_litellm_stream.py`: Exercises raw stream completion loops using LiteLLM.
*   `test_llm.py`: Quick verification script checking model connection latency and API key health.
*   `test_monkey_stream.py`: Monkey-patching experiment on standard CrewAI classes to custom-capture stream prints.
*   `test_patch.py`: Validates monkey patching behavior.
*   `test_stream_true.py`: Test specifically for testing dynamic text streaming when `stream=True` is enabled.
