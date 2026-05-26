# Migration: CrewAI → Native LiteLLM Tool-Calling Loop

Replace CrewAI's text-based ReAct loop with a native `litellm` streaming loop using OpenAI-compatible function calling. The frontend stays untouched — we emit the exact same SSE events.

---

## Why Each Piece Changes

The migration has **4 layers**, bottom-up:

1. **Tool Layer** — Tools must speak OpenAI function-calling JSON instead of CrewAI's `BaseTool`
2. **Loop Engine** — A new `run_agent_loop()` replaces CrewAI's `Crew.kickoff()`
3. **Endpoints** — The 3 agent endpoints rewire to call the new loop
4. **Dead Code** — Delete everything that only existed to work around CrewAI

---

## User Review Required

> [!WARNING]
> This replaces the entire backend orchestration engine. The tool implementations (terminal exec, file I/O, approval flow) stay identical — only the layer that *calls* them changes. The frontend is untouched since the SSE event vocabulary remains the same.

> [!IMPORTANT]
> **Dependency change:** After this, `crewai` and `langchain-core` can be removed from `requirements.txt` / your venv. The only LLM dependency will be `litellm`.

## Open Questions

> [!NOTE]
> **Token context management:** CrewAI currently resends the full task description on every iteration of the ReAct loop (this is what caused your 1.8M token explosion documented in the CHANGELOG). With native control, we can choose: (a) only send the system prompt once + accumulate tool results, or (b) implement a sliding window. I'll go with (a) by default — the standard OpenAI messages array pattern — which is already far more efficient. Let me know if you want something fancier.

---

## Proposed Changes

---

### Layer 1: Tool Layer

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

**Why:** Every tool currently inherits from `crewai.tools.BaseTool` and implements `_run()`. The native loop needs two things instead: (1) an OpenAI-format JSON schema to tell the LLM what tools exist, and (2) a plain Python callable to execute when the LLM invokes one.

**Changes:**
- Remove `from crewai.tools import BaseTool` import
- Change each tool class to inherit from a simple base class we define (or just be standalone classes)
- Add a `to_openai_schema()` method on each tool that converts its existing Pydantic `args_schema` into the OpenAI function-calling format:
  ```python
  {
      "type": "function",
      "function": {
          "name": "execute_terminal_command",
          "description": "...",
          "parameters": { ... }  # from Pydantic model_json_schema()
      }
  }
  ```
- Keep the `_run()` methods and their return strings **completely unchanged** — the LLM gets the same feedback
- Add a `ToolRegistry` class that holds all tool instances and provides:
  - `get_schemas()` → list of OpenAI tool schemas for the API call
  - `execute(tool_name, args_dict)` → dispatches to the right tool's `_run()`
  - `get_tool(name)` → lookup by name

**Why not just use plain functions?** Because the tools carry state (workspace_path, approval_callback, stream_callback). Keeping them as classes preserves the existing constructor patterns.

---

#### [MODIFY] [design_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/design_tools.py)

**Why:** Same reason — remove CrewAI dependency, add OpenAI schema export.

**Changes:**
- Remove `BaseTool` inheritance
- Add `to_openai_schema()` to `UpdateSpecTool`
- Keep `_run()` unchanged

---

### Layer 2: Loop Engine (new code in main.py)

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py) — Add `run_agent_loop()`

**Why:** This is the core replacement for `Crew.kickoff()`. CrewAI's loop works by printing `Thought:` / `Action:` / `Observation:` to stdout, which we then regex-parse with `StreamCatcher`. The new loop uses native function calling — the LLM returns structured JSON tool calls, we execute them, and feed results back. No text parsing needed.

**The loop works like this:**

```
messages = [system_prompt, user_task]

while iterations < max_iter:
    response = litellm.completion(messages, tools, stream=True)

    # Stream and accumulate the response
    for chunk in response:
        if chunk has reasoning_content → emit SSE "model_thinking"
        if chunk has content → accumulate text (this becomes a "thought")
        if chunk has tool_calls → accumulate tool call args

    if response has text content (no tool calls):
        → This is the final answer. Emit "final_answer", break.

    if response has tool_calls:
        for each tool_call:
            → emit SSE "tool_call" (tool name)
            → emit SSE "tool_input" (args)
            → if HITL enabled: emit "action_required", wait for approval
            → execute tool via ToolRegistry
            → emit SSE "tool_result"
            → append tool result to messages

    iterations++

if iterations >= max_iter:
    → emit "system" warning about hitting iteration limit
```

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| Stream with `stream=True` | Lets us emit `model_thinking` tokens in real-time, same as current `PatchedStream` but without the monkeypatch |
| Accumulate full response before executing | Matches OpenAI's pattern — tool calls arrive across multiple chunks and need to be assembled |
| Single function, not a class | The loop is stateless between calls. All state (messages, tools, queue, abort_event) is passed in as args |
| Max iterations parameter | Safety valve replacing CrewAI's `max_iter=75` / `max_iter=50` |

**Parameters:**
```python
async def run_agent_loop(
    system_prompt: str,        # from agents.yaml → converted to prose
    task_description: str,     # the user's spec/task
    tool_registry: ToolRegistry,
    model: str,                # litellm model string
    q: queue.Queue,            # SSE event queue
    abort_event: threading.Event,
    approval_callback: Callable,
    max_iter: int = 75,
    llm_kwargs: dict = {},     # reasoning_effort, etc.
) -> dict:                     # {status, summary, usage}
```

---

### Layer 3: Endpoint Rewiring

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py) — `/api/design/chat`

**Why:** Currently creates a CrewAI `Agent` + `Task` + `Crew` just to call the LLM once with a tool. Since the design endpoint is a single-turn call (not a loop), we can simplify it to a plain `litellm.completion()` with function calling.

**Changes:**
- Remove CrewAI Agent/Task/Crew construction
- Build the system prompt from `agents.yaml["designer"]` fields (role + backstory + goal → single system message)
- Call `litellm.completion()` with the `UpdateSpec` tool schema
- If the LLM returns a tool call → extract the spec and summary from the args
- If the LLM returns text → fall back to raw output (same as current behavior)
- No loop needed — design is single-turn

---

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py) — `/api/develop`

**Why:** Currently the biggest mess — `run_crew()` is a 150-line function that hijacks stdout, creates a CrewAI crew, and relies on `StreamCatcher` to parse all output.

**Changes:**
- Delete `run_crew()` entirely
- Build system prompt from `agents.yaml["developer"]` fields
- Create `ToolRegistry` with all dev tools
- Call `run_agent_loop()` in a background thread
- The SSE `event_generator()` stays exactly the same — it just reads from `q`

---

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py) — `/api/dev-iterate`

**Why:** `run_iterate()` is a near-copy of `run_crew()` with a different system prompt. Same treatment.

**Changes:**
- Delete `run_iterate()` entirely
- Build system prompt from `agents.yaml["iterative_developer"]` fields
- Inject `dev_context` into the task description (same as current)
- Call `run_agent_loop()` in a background thread

---

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py) — System Prompt Migration

**Why:** CrewAI constructs a system prompt internally from the agent's `role`, `goal`, and `backstory` fields in `agents.yaml`. We need to do this ourselves now.

**Approach:** Build a system prompt string from the YAML config:
```python
def build_system_prompt(agent_config: dict, workspace_path: str, extra_context: str = "") -> str:
    return f"""You are a {agent_config['role']}.

Your goal: {agent_config['goal']}

Background: {agent_config['backstory']}

Workspace: {workspace_path}
{extra_context}

When you have completed the task, provide your final summary as a text response (do not call any tools).
When reporting results, be specific about what files were created/modified."""
```

The YAML file stays as-is — we just read it differently.

---

### Layer 4: Dead Code Removal

#### [DELETE from main.py] — `StreamCatcher` class (~100 lines)

**Why:** This existed solely to intercept CrewAI's `print()` output and regex-match `Thought:`, `Action:`, `Action Input:`, `Observation:`, `Final Answer:`. With native function calling, the LLM returns structured tool calls as JSON. There is nothing to parse from stdout.

---

#### [DELETE from main.py] — `PatchedStream` class + `_patched_completion` + `_litellm.completion = _patched_completion`

**Why:** This monkeypatch of litellm's global `completion` function existed to intercept `reasoning_content` (thinking tokens) from streaming responses. The new `run_agent_loop()` handles this natively when iterating over stream chunks — no monkeypatch needed.

---

#### [DELETE from main.py] — `CustomStreamCallback(BaseCallbackHandler)`

**Why:** This was a LangChain callback handler (note the import: `from langchain_core.callbacks import BaseCallbackHandler`). It was attached to CrewAI's LLM to try to capture thinking tokens. No longer needed since we stream directly.

---

#### [DELETE from main.py] — `_thread_local` usage

**Why:** This thread-local storage was used to pass the SSE queue to the monkeypatched `_patched_completion`. The new loop receives the queue as a direct parameter. Clean.

---

#### [DELETE] [agent_workflow.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/agent_workflow.py)

**Why:** Standalone CrewAI demo script from early development. Dead code.

---

#### [MODIFY] Imports in main.py

**Remove:**
```python
from crewai import Agent, Task, Crew, LLM
from langchain_core.callbacks import BaseCallbackHandler
import yaml  # only if agents.yaml is kept as-is; actually we still need this
```

**Keep:**
```python
import litellm  # already imported as _litellm
import yaml     # still reading agents.yaml
```

---

### Bonus: Per-Request State Isolation

**Why:** The current code has process-global `abort_event` and `approval_state` with TODO comments acknowledging they'll break with concurrent users. While we're rewiring the loop, we can fix this cheaply.

**Changes:**
- Create a `RunState` dataclass:
  ```python
  @dataclass
  class RunState:
      abort_event: threading.Event
      approval_event: threading.Event
      approved: bool = False
      feedback: str | None = None
  ```
- Each `/api/develop` and `/api/dev-iterate` call creates its own `RunState` and stores it in a dict keyed by `run_id` (a UUID)
- The SSE stream returns the `run_id` in the first event
- `/api/develop/stop`, `/api/develop/approve` take a `run_id` parameter
- Frontend sends `run_id` back with stop/approve requests

> [!NOTE]
> This is a nice-to-have for now since this is a single-user local tool. I'll implement the basic version (create RunState per request) but keep the frontend changes minimal — just thread the run_id through. We can skip it entirely if you'd rather keep scope tight.

---

## Files Summary

| File | Action | Why |
|------|--------|-----|
| [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py) | Modify | Remove CrewAI base class, add OpenAI schema export + tool registry |
| [design_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/design_tools.py) | Modify | Same — remove CrewAI, add schema |
| [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py) | Heavy modify | New `run_agent_loop()`, rewire 3 endpoints, delete ~300 lines of glue |
| [agent_workflow.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/agent_workflow.py) | Delete | Dead CrewAI demo |
| [config/agents.yaml](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/config/agents.yaml) | Keep as-is | Still used, just read differently |
| Frontend (`page.tsx`, `Terminal.tsx`, etc.) | **No changes** | SSE event types unchanged |

---

## Verification Plan

### Automated
- Run the backend with `python main.py` and verify startup without import errors
- Hit `/api/settings` to confirm the server is alive

### Manual — Design Chat
- Send a design idea through the UI → verify the spec tab updates
- Confirm `UpdateSpecTool` is called via function calling (check backend logs)

### Manual — Full Build
- Click "Build from Spec" with a simple spec → watch Terminal UI
- Verify these SSE events render correctly:
  - `model_thinking` (purple thinking tokens, if thinking level is set)
  - `thought` (agent's text reasoning)  
  - `tool_call` + `tool_input` (tool invocations)
  - `cmd_start` + `cmd_output` + `cmd_end` (live terminal streaming)
  - `tool_result` (collapsible result cards)
  - `final_answer` (agent summary)
  - `result` (agent result panel)

### Manual — HITL
- Enable approval toggle → verify `action_required` pauses the loop
- Click Approve → verify the loop resumes
- Click Reject with feedback → verify the agent receives the feedback and adapts

### Manual — Stop Button
- Click Stop mid-build → verify the stream terminates cleanly with a `killed` status
