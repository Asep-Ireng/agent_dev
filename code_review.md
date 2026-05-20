# Code Review — `agent_dev` Recent Changes

---

## 🔴 Bugs & Active Issues

### 1. Same `.get()` Bug Exists in Two More Places
You fixed line 312 in `/api/design/chat`, but the **exact same bug** is still live in `run_crew()` and `run_iterate()`:

```diff
# main.py:874-877 (inside run_crew / /api/develop)
- "prompt_tokens": crew.usage_metrics.get("prompt_tokens", 0),
- "completion_tokens": crew.usage_metrics.get("completion_tokens", 0),
- "total_tokens": crew.usage_metrics.get("total_tokens", 0),

# main.py:1208-1211 (inside run_iterate / /api/dev-iterate)
- "prompt_tokens": crew.usage_metrics.get("prompt_tokens", 0),
- "completion_tokens": crew.usage_metrics.get("completion_tokens", 0),
- "total_tokens": crew.usage_metrics.get("total_tokens", 0),
```

These will crash with the same `AttributeError: 'UsageMetrics' object has no attribute 'get'` whenever the crew runs successfully and tries to emit token metrics in the `done` event. You just haven't hit them yet because these paths fire from background threads, and the error gets swallowed into the SSE `done` event with `errored = True`.

> [!CAUTION]
> **Fix immediately.** Change all `.get()` calls on `crew.usage_metrics` to `getattr()`. There are exactly **2 more** occurrences at [main.py:874](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L874) and [main.py:1208](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L1208).

---

### 2. Global `abort_event` Is Shared Across All Requests
[main.py:36](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L36) — There's a single global `abort_event = threading.Event()`. If two browser tabs are open, or someone accidentally double-clicks "Build", aborting one run will kill all concurrent runs. Same issue with `approval_state` at [line 39](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L39).

> [!WARNING]
> Not critical for single-user local dev, but becomes a showstopper if you ever deploy this or run parallel builds. Consider generating a per-request `run_id` and keying events off that.

---

### 3. Operator Precedence Bug in StreamCatcher
[main.py:588-591](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L588-L591):

```python
if (
    clean.startswith("Observation:")
    or "Tool" in clean
    and "executed with result" in clean
):
```

Due to Python's operator precedence, `and` binds tighter than `or`. This evaluates as:
```python
clean.startswith("Observation:") or ("Tool" in clean and "executed with result" in clean)
```

That happens to be correct *for this case*, but it's ambiguous and fragile. Add explicit parentheses to make the intent clear. If you actually wanted `(startswith(...) or "Tool" in clean) and "executed with result" in clean`, you have a different bug entirely.

---

## 🟡 DRY Violations — Massive Code Duplication

### 4. `StreamCatcher` Is Copy-Pasted Twice
The `StreamCatcher` class inside [run_crew()](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L525) (lines 525–704) and [run_iterate()](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L922) (lines 922–1048) are nearly identical — ~120 lines of duplicated parsing logic. The only difference is that the `run_crew` version has a slightly more detailed `_emit_tool_result()` method with extra cases for `write_file` and `unknown`.

> [!IMPORTANT]
> Extract `StreamCatcher` to a **module-level class** that takes `q` as a constructor arg. This is the single biggest maintainability issue — any fix to one has to be manually applied to the other.

### 5. Tool Instantiation Block Is Duplicated
The block creating `terminal_tool`, `write_file_tool`, `read_file_tool`, etc. (lines 755–788 and 1091–1119) is identical across both endpoints. Same pattern — extract to a factory function:

```python
def create_tools(workspace_path, require_approval, approval_callback, stream_callback):
    return {
        "terminal": TerminalExecutionTool(workspace_path=workspace_path, ...),
        "write_file": WriteFileTool(workspace_path=workspace_path, ...),
        ...
    }
```

### 6. SSE Stream Processing Is Duplicated on the Frontend
[page.tsx:149-229](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L149-L229) (`handleDevelop`) and [page.tsx:492-595](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L492-L595) (`handleApplyProceed`) both implement full SSE stream parsing with nearly identical logic. Extract a shared `processSSEStream(reader, onEvent, onDone)` utility.

### 7. Token Accumulation Pattern Repeated 5 Times
The same `setTotalTokens((prev) => ({ prompt: prev.prompt + ..., ... }))` block appears at lines [111](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L111), [175](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L175), [392](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L392), [437](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L437), and [579](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L579). Extract:

```typescript
const accumulateTokens = (usage: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }) => {
  setTotalTokens((prev) => ({
    prompt: prev.prompt + (usage.prompt_tokens || 0),
    completion: prev.completion + (usage.completion_tokens || 0),
    total: prev.total + (usage.total_tokens || 0),
  }));
};
```

---

## 🟠 Architecture & Performance

### 8. `sys.stdout` Redirect Is Thread-Unsafe
[main.py:712](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/main.py#L712) — You're doing `sys.stdout = StreamCatcher()` inside a background thread. `sys.stdout` is a **process-global**, so if the develop and iterate endpoints are called concurrently (or even if FastAPI logs something from its own threads), the output gets jumbled or swallowed.

Consider using `contextlib.redirect_stdout()` in combination with a thread-local, or better yet, hook into CrewAI's callback system instead of monkeypatching stdout.

### 9. Terminal Renders Every Log Entry Every Frame
[Terminal.tsx:109](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/components/Terminal.tsx#L109) — The map runs over the entire `actionLogs` array on every render. During a 75-step agent run, you'll have hundreds (sometimes thousands) of log entries, and every new `addLog` call triggers a full re-render of the entire list.

Fix: Wrap individual log items in `React.memo` components, or use virtualized rendering (`react-window` / `react-virtuoso`). At minimum, memoize the log renderer.

### 10. `addLog` Creates a New Array Every Call
[page.tsx:137-139](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L137-L139):
```typescript
const addLog = (entry: LogEntry) => {
  setActionLogs((prev) => [...prev, entry]);
};
```

During heavy agent output, this creates a new array copy for every single log line. Combined with React's batching (or lack thereof during SSE), this can cause visible frame drops. Use a `useRef`-based buffer that flushes periodically:

```typescript
const logBuffer = useRef<LogEntry[]>([]);
const addLog = (entry: LogEntry) => { logBuffer.current.push(entry); };
// flush every 100ms via requestAnimationFrame
```

---

## 🟢 Smaller Issues & Style

### 11. `model_thinking` Events Not Handled in `handleApplyProceed`
[page.tsx:515-544](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L515-L544) — The iterate stream handler handles `thought`, `tool_call`, etc. but doesn't have a case for `model_thinking`. So when thinking is enabled, model thinking tokens from the iterate path will be silently dropped and not show in the terminal.

### 12. Hardcoded `localhost:8000` Everywhere
[page.tsx](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx) has `http://localhost:8000` hardcoded in at least **9 places**. Pull this into an env var or a constants file:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

### 13. DesignChat Uses Raw Text Instead of Markdown
[DesignChat.tsx:59](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/components/DesignChat.tsx#L59) — Agent messages are rendered as `{msg.content}` raw. But `AgentResult` uses `<ReactMarkdown>`. If the designer agent returns markdown-formatted content (which it often will), it'll display as plain text with literal asterisks and hashes.

### 14. DesignChat Send Button Gradient Is a No-Op
[DesignChat.tsx:158](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/components/DesignChat.tsx#L158):
```jsx
className="bg-gradient-to-r from-[#E51937] to-[#E51937]"
```
A gradient from a color to itself is just a solid fill. Either make it an actual gradient or just use `bg-[#E51937]`.

### 15. Scroll-to-Top Button Won't Work
[page.tsx:777](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L777):
```jsx
onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
```
The `<main>` element has `overflow-y-auto`, making it the scroll container — not `window`. `window.scrollTo` won't scroll anything because the window itself doesn't overflow. You need a ref to the main element:
```jsx
mainRef.current?.scrollTo({ top: 0, behavior: "smooth" })
```

### 16. `dangerouslySetInnerHTML` for Scrollbar CSS
[page.tsx:784-793](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/frontend/src/app/page.tsx#L784-L793) — Using `dangerouslySetInnerHTML` to inject CSS is a code smell. Move it to your global CSS file (`globals.css` or `index.css`). It'll also stop re-injecting on every render.

---

## Summary Table

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | 🔴 Bug | `main.py:874, 1208` | `.get()` on Pydantic `UsageMetrics` — will crash |
| 2 | 🟡 Race | `main.py:36` | Global `abort_event` shared across requests |
| 3 | 🟡 Bug | `main.py:588` | Operator precedence ambiguity |
| 4 | 🟡 DRY | `main.py` | `StreamCatcher` duplicated 2x (~240 lines) |
| 5 | 🟡 DRY | `main.py` | Tool instantiation duplicated |
| 6 | 🟡 DRY | `page.tsx` | SSE processing duplicated |
| 7 | 🟢 DRY | `page.tsx` | Token accumulation repeated 5x |
| 8 | 🟠 Thread | `main.py:712` | `sys.stdout` redirect is process-global |
| 9 | 🟠 Perf | `Terminal.tsx` | Full re-render on every log |
| 10 | 🟠 Perf | `page.tsx` | Array copy per log line |
| 11 | 🟡 Bug | `page.tsx:515` | `model_thinking` dropped in iterate handler |
| 12 | 🟢 Maint | `page.tsx` | Hardcoded `localhost:8000` x9 |
| 13 | 🟢 UX | `DesignChat.tsx` | Agent messages not markdown-rendered |
| 14 | 🟢 Style | `DesignChat.tsx:158` | No-op gradient |
| 15 | 🟡 Bug | `page.tsx:777` | Scroll-to-top targets wrong container |
| 16 | 🟢 Style | `page.tsx:784` | `dangerouslySetInnerHTML` for CSS |
