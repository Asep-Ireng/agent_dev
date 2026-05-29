# Fix All 16 Code Review Issues

Comprehensive plan to address every issue from [code_review.md](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/code_review.md). Grouped by priority tier.

---

## Open Questions

> [!IMPORTANT]
> **Issue #2 (Global `abort_event`)** — The review flags this as a race condition for concurrent requests. Do you want me to implement per-request `run_id` keying now, or defer it since this is single-user local dev? Implementing it properly touches the stop/approve/toggle endpoints too. I'd recommend deferring and just adding a `# TODO` comment for now.

> [!IMPORTANT]
> **Issue #8 (`sys.stdout` redirect)** — The proper fix is to hook into CrewAI's callback system instead of monkeypatching stdout. However, CrewAI's ReAct output parsing relies on stdout capture. A safer middle-ground is wrapping the redirect in a `threading.local()` or using `contextlib.redirect_stdout`. Which approach do you prefer? I'd lean toward `contextlib.redirect_stdout` inside the thread since it's scoped, but it's still process-global under the hood. Adding a `# TODO` with the caveat might be the pragmatic call here too.

> [!IMPORTANT]
> **Issue #9 (Terminal virtualization)** — Full virtualization (`react-window`/`react-virtuoso`) adds a dependency and complexity. The simpler fix is `React.memo` on log items + the buffered `addLog` from Issue #10. Want me to go full virtualization or just the memo + buffer approach?

---

## Tier 1 — 🔴 Critical Bugs (Fix Immediately)

### Backend

---

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py)

**Issue #1: `.get()` → `getattr()` at lines 874-877 and 1208-1211**

Both `run_crew()` and `run_iterate()` call `crew.usage_metrics.get(...)` — `UsageMetrics` is a Pydantic model, not a dict. Change to `getattr()` to match the fix already applied at line 312.

```diff
# Line 874-877 (run_crew)
-"prompt_tokens": crew.usage_metrics.get("prompt_tokens", 0),
-"completion_tokens": crew.usage_metrics.get("completion_tokens", 0),
-"total_tokens": crew.usage_metrics.get("total_tokens", 0),
+"prompt_tokens": getattr(crew.usage_metrics, "prompt_tokens", 0),
+"completion_tokens": getattr(crew.usage_metrics, "completion_tokens", 0),
+"total_tokens": getattr(crew.usage_metrics, "total_tokens", 0),

# Line 1208-1211 (run_iterate) — same change
```

**Issue #3: Operator precedence in StreamCatcher (line 588-591)**

Add explicit parentheses. The current logic happens to be correct, but it's fragile:

```diff
-if (
-    clean.startswith("Observation:")
-    or "Tool" in clean
-    and "executed with result" in clean
-):
+if (
+    clean.startswith("Observation:")
+    or ("Tool" in clean and "executed with result" in clean)
+):
```

---

## Tier 2 — 🟡 DRY Refactors

### Backend

---

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py)

**Issue #4: Extract `StreamCatcher` to module level**

Move `StreamCatcher` out of both `run_crew()` and `run_iterate()` into a single module-level class that takes `q` (the queue) and `_emit` as constructor args. Both `run_crew` and `run_iterate` will instantiate the same class. The `run_crew` version's `_emit_tool_result` with `write_file` and `unknown` cases is the more complete one — that becomes the canonical implementation.

```python
class StreamCatcher:
    """Captures CrewAI stdout, parses ReAct patterns, and emits typed SSE events."""

    def __init__(self, q: queue.Queue):
        self.q = q
        self.buffer = ""
        self.in_thinking = False

    def write(self, text):
        # ... unified parsing logic (from run_crew version, which is more complete)

    def _emit_tool_result(self, text):
        # ... full version with terminal, write_file, and generic cases

    def flush(self):
        pass
```

**Issue #5: Extract tool creation to factory function**

Create `create_dev_tools(workspace_path, require_approval, approval_callback, stream_callback, task_status)` that returns the list of tool instances. Called from both `run_crew` and `run_iterate`.

```python
def create_dev_tools(workspace_path, require_approval, approval_callback, stream_callback, task_status):
    return [
        TerminalExecutionTool(workspace_path=workspace_path, require_approval=require_approval, approval_callback=approval_callback, stream_callback=stream_callback),
        WriteFileTool(workspace_path=workspace_path, require_approval=require_approval, approval_callback=approval_callback),
        ReadFileTool(workspace_path=workspace_path),
        ReplaceInFileTool(workspace_path=workspace_path, require_approval=require_approval, approval_callback=approval_callback),
        EditFileLinesTool(workspace_path=workspace_path, require_approval=require_approval, approval_callback=approval_callback),
        InsertAtLineTool(workspace_path=workspace_path, require_approval=require_approval, approval_callback=approval_callback),
        ReportTaskStatusTool(result_holder=task_status),
    ]
```

### Frontend

---

#### [MODIFY] [page.tsx](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx)

**Issue #7: Extract `accumulateTokens` helper**

Define once, use in all 5 places:

```typescript
const accumulateTokens = (usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }) => {
  setTotalTokens((prev) => ({
    prompt: prev.prompt + (usage.prompt_tokens || 0),
    completion: prev.completion + (usage.completion_tokens || 0),
    total: prev.total + (usage.total_tokens || 0),
  }));
};
```

**Issue #6: Extract shared SSE processing**

The `processSSEStream` function in `handleDevelop` (lines 149-229) and `handleApplyProceed` (lines 492-595) are nearly identical. Extract a shared utility. The `handleApplyProceed` version has inline event handling, so I'll unify both to use a callback-based approach:

```typescript
const processSSEStream = async (
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (eventType: string, data: Record<string, unknown>) => void,
  onDone: (data: Record<string, unknown>) => void,
) => { ... };
```

Both `handleDevelop` and `handleApplyProceed` will call this with their specific `onEvent`/`onDone` callbacks.

---

## Tier 3 — 🟠 Architecture & Performance

### Frontend

---

#### [MODIFY] [page.tsx](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx)

**Issue #10: Buffered `addLog`**

Replace the array-copy-per-call `addLog` with a `useRef` buffer that flushes every ~100ms:

```typescript
const logBufferRef = useRef<LogEntry[]>([]);
const flushTimerRef = useRef<number | null>(null);

const addLog = (entry: LogEntry) => {
  logBufferRef.current.push(entry);
  if (!flushTimerRef.current) {
    flushTimerRef.current = requestAnimationFrame(() => {
      setActionLogs((prev) => [...prev, ...logBufferRef.current]);
      logBufferRef.current = [];
      flushTimerRef.current = null;
    });
  }
};
```

#### [MODIFY] [Terminal.tsx](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/components/Terminal.tsx)

**Issue #9: Memoize log items**

Extract each log case into a `React.memo` component (`LogItem`) to prevent full-list re-render:

```typescript
const LogItem = React.memo(({ log, idx, ... }: { log: LogEntry; idx: number; ... }) => {
  switch (log.type) { ... }
});
```

---

## Tier 4 — 🟢 Smaller Issues & Style

### Frontend

---

#### [MODIFY] [page.tsx](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx)

**Issue #12: Extract `API_BASE` constant**

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

Replace all 9 hardcoded `http://localhost:8000` instances.

**Issue #15: Fix scroll-to-top**

Add a `mainRef` to the `<main>` element and use it instead of `window.scrollTo`:

```diff
+const mainRef = useRef<HTMLElement>(null);
 ...
-<main className="flex-1 overflow-y-auto p-10 relative bg-grid">
+<main ref={mainRef} className="flex-1 overflow-y-auto p-10 relative bg-grid">
 ...
-onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
+onClick={() => mainRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
```

**Issue #16: Move scrollbar CSS to globals.css**

Remove the `<style dangerouslySetInnerHTML>` block and add the scrollbar styles to [globals.css](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/globals.css).

**Issue #11: Handle `model_thinking` in iterate handler**

Add the missing case in the `handleApplyProceed` SSE handler (will be in the unified handler after Issue #6 refactor — but making sure it's there):

```typescript
case "model_thinking":
  addLog({ type: "model_thinking", text: data.text as string });
  break;
```

#### [MODIFY] [DesignChat.tsx](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/components/DesignChat.tsx)

**Issue #13: Render agent messages as markdown**

Import `ReactMarkdown` and use it for agent messages instead of raw text:

```diff
-{msg.content}
+{msg.role === "agent" ? <ReactMarkdown>{msg.content}</ReactMarkdown> : msg.content}
```

**Issue #14: Fix no-op gradient**

```diff
-className="bg-gradient-to-r from-[#E51937] to-[#E51937]"
+className="bg-gradient-to-r from-[#E51937] to-[#FF4D6A]"
```

### Backend

---

#### [MODIFY] [main.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py)

**Issue #2: Add TODO comment for global abort_event**

```python
# TODO: abort_event and approval_state are process-global — concurrent requests
# will interfere. Implement per-request run_id keying if deploying multi-user.
abort_event = threading.Event()
```

**Issue #8: Add TODO comment for sys.stdout**

```python
# TODO: sys.stdout is process-global — concurrent threads will jumble output.
# Consider hooking into CrewAI's callback system or using thread-local redirection.
sys.stdout = StreamCatcher(q)
```

---

## Verification Plan

### Automated Tests
1. `python -c "from main import app; print('Backend imports OK')"` — verify no syntax errors after refactor
2. Start backend with `uvicorn main:app` and hit `/api/settings` to verify it boots
3. Run `npx next build` in frontend to catch TypeScript errors

### Manual Verification
- Trigger a design chat and verify token counting still works
- Trigger a develop run and verify terminal streaming, tool results, and the done event all fire correctly
- Trigger an iterate run (via dev chat apply mode) and verify `model_thinking` events now appear
- Verify scroll-to-top button actually scrolls the main container
- Check DesignChat agent messages render markdown properly
- Confirm the send button has a visible gradient now

---

## Summary Table

| # | Severity | Approach | Effort |
|---|----------|----------|--------|
| 1 | 🔴 Bug | `.get()` → `getattr()` x2 | Trivial |
| 3 | 🟡 Bug | Add parens | Trivial |
| 4 | 🟡 DRY | Extract `StreamCatcher` to module-level | Medium |
| 5 | 🟡 DRY | Extract `create_dev_tools()` factory | Small |
| 6 | 🟡 DRY | Extract shared `processSSEStream` utility | Medium |
| 7 | 🟢 DRY | Extract `accumulateTokens` helper | Trivial |
| 9 | 🟠 Perf | `React.memo` on log items | Small |
| 10 | 🟠 Perf | Buffered `addLog` with `requestAnimationFrame` | Small |
| 11 | 🟡 Bug | Add `model_thinking` case | Trivial |
| 12 | 🟢 Maint | `API_BASE` constant | Trivial |
| 13 | 🟢 UX | `ReactMarkdown` for agent messages | Small |
| 14 | 🟢 Style | Fix gradient colors | Trivial |
| 15 | 🟡 Bug | `mainRef.scrollTo` | Trivial |
| 16 | 🟢 Style | Move CSS to globals.css | Trivial |
| 2 | 🟡 Race | TODO comment (deferred) | Trivial |
| 8 | 🟠 Thread | TODO comment (deferred) | Trivial |
