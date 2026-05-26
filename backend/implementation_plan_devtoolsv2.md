# Devtools Safety Hardening — Revised Implementation Plan

Enhance the agent's file editing and command execution tools in [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py) to prevent codebase corruption, unsafe command execution, and runaway retry loops.

> [!NOTE]
> This is a **revised version** of [Flash's original plan](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/implementation_plan_optimize_devtools.md). The core ideas (AST validation, batch edits, transactions) are preserved. The naive JS bracket counting, missing safety features, and architectural concerns have been addressed.

---

## What Changed From Flash's Plan

| Aspect | Flash's Plan | This Revision |
|--------|-------------|---------------|
| Python/JSON validation | ✅ `ast.parse()` + `json.loads()` | ✅ Kept as-is |
| JS/TS/HTML/CSS validation | ❌ Naive bracket counting | 🚫 **Dropped** — false positives on template literals, JSX, string content. Agent catches these via `npm run dev` anyway |
| Batch edit tool | ✅ Bottom-to-top transaction | ✅ Kept, with added file lock |
| Anchor content on edits | 🟡 Optional `anchor_content` param | 🟡 **Deferred** — duplicates `replace_in_file` behavior, burns extra tokens |
| Terminal command safety | ❌ Not mentioned | ✅ **Added** — blocklist + workspace-only cwd |
| File size limits | ❌ Not mentioned | ✅ **Added** — 2MB cap on writes |
| Concurrent edit protection | ❌ Not mentioned | ✅ **Added** — per-file threading lock |
| Retry budget | ❌ Not mentioned | ✅ **Added** — max 3 validation failures per file per run |
| Code organization | All in `dev_tools.py` | Validation logic in new `syntax_guard.py` |

---

## User Review Required

> [!IMPORTANT]
> **Tool names are preserved.** `write_file`, `replace_in_file`, `edit_file_lines`, `insert_at_line` — all keep their exact names and existing parameters. The only new tool is `batch_replace_file_content`. Existing agent system prompts and backstories require zero changes.

> [!WARNING]
> **Terminal command blocklist is opinionated.** The proposed blocklist blocks commands like `rm -rf /`, `format`, `del /s /q`, `shutdown`, etc. But the agent legitimately needs to run `rm` for cleanup. The blocklist targets *dangerous patterns* (recursive root deletion, system commands), not the commands themselves. Review the specific patterns below and tell me if anything needs adjusting.

> [!IMPORTANT]
> **JS/TS syntax validation is deliberately omitted.** Flash proposed naive bracket counting — I'm dropping it because it will false-positive on valid JSX, template literals, and string content constantly. The agent already validates JS by running `npm run dev` / `npx next build`. If you want JS validation later, we'd need `tree-sitter` bindings or a subprocess call to `acorn`, which is a bigger undertaking.

---

## Open Questions

> [!IMPORTANT]
> **File size cap**: I'm proposing 2MB. Is that reasonable for your use case? Some generated bundles or large JSON fixtures could exceed this. Should certain extensions (`.json`, `.lock`) get a higher cap?

> [!IMPORTANT]
> **Retry budget scope**: Should the "3 failures per file" counter reset between agent iterations, or persist for the entire run? Resetting per-iteration is more lenient but risks infinite loops; persisting is safer but might block the agent on a legitimately hard edit.

---

## Proposed Changes

### New Module: Syntax Validation

#### [NEW] [syntax_guard.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/syntax_guard.py)

A standalone validation module. Keeps `dev_tools.py` focused on tool logic.

```python
"""
syntax_guard.py — Pre-write syntax validation for agent file operations.

Validates file content before committing to disk. Supports:
- Python (.py): ast.parse()
- JSON (.json): json.loads()

Returns None on success, or a descriptive error string on failure.
"""

import ast
import json
import os
import threading
from collections import defaultdict

# Per-file failure tracking: {file_path: count}
_failure_counts: dict[str, int] = defaultdict(int)
_failure_lock = threading.Lock()
MAX_FAILURES_PER_FILE = 3

# Maximum file size (bytes) — reject writes larger than this
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB


def validate_file_content(file_path: str, content: str) -> str | None:
    """Validate content before writing. Returns error string or None."""
    
    # Check file size
    content_bytes = len(content.encode("utf-8"))
    if content_bytes > MAX_FILE_SIZE_BYTES:
        return (
            f"[REJECTED] File too large: {content_bytes:,} bytes "
            f"(max {MAX_FILE_SIZE_BYTES:,}). "
            f"Break the file into smaller modules."
        )
    
    # Check retry budget
    with _failure_lock:
        if _failure_counts[file_path] >= MAX_FAILURES_PER_FILE:
            return (
                f"[REJECTED] Too many failed validation attempts on {file_path} "
                f"({MAX_FAILURES_PER_FILE} failures). "
                f"Read the file again, rethink your approach, or use a different strategy."
            )
    
    ext = os.path.splitext(file_path)[1].lower()
    error = None
    
    if ext == ".py":
        error = _validate_python(content, file_path)
    elif ext == ".json":
        error = _validate_json(content, file_path)
    
    # Track failures
    if error:
        with _failure_lock:
            _failure_counts[file_path] += 1
            remaining = MAX_FAILURES_PER_FILE - _failure_counts[file_path]
            error += f"\n({remaining} attempt(s) remaining for this file)"
    
    return error


def reset_failure_counts():
    """Reset all failure counters. Call at the start of a new run."""
    with _failure_lock:
        _failure_counts.clear()


def _validate_python(content: str, file_path: str) -> str | None:
    try:
        ast.parse(content, filename=file_path)
        return None
    except SyntaxError as e:
        return (
            f"[SYNTAX ERROR] Python validation failed for {file_path}:\n"
            f"  Line {e.lineno}, Col {e.offset}: {e.msg}\n"
            f"  {e.text.strip() if e.text else ''}\n"
            f"Fix the syntax error before saving. The file was NOT written."
        )


def _validate_json(content: str, file_path: str) -> str | None:
    try:
        json.loads(content)
        return None
    except json.JSONDecodeError as e:
        return (
            f"[SYNTAX ERROR] JSON validation failed for {file_path}:\n"
            f"  Line {e.lineno}, Col {e.colno}: {e.msg}\n"
            f"Fix the JSON error before saving. The file was NOT written."
        )
```

**Key design decisions:**
- Python and JSON only — no naive JS/TS validation
- Retry budget tracked per-file with a thread-safe counter
- File size cap at 2MB with a clear error message
- `reset_failure_counts()` called at run start to prevent stale state

---

### Terminal Command Sandboxing

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

Add a command safety check to `TerminalExecutionTool.run()`:

```python
# Dangerous command patterns — block these regardless of context
BLOCKED_COMMAND_PATTERNS = [
    r"rm\s+-rf\s+/(?!\S)",          # rm -rf / (but not rm -rf /some/path)
    r"del\s+/s\s+/q\s+[A-Z]:\\$",   # del /s /q C:\ 
    r"format\s+[A-Z]:",             # format C:
    r"shutdown",                     # shutdown
    r"mkfs\.",                       # mkfs.ext4 etc
    r":(){",                         # fork bomb
    r">\s*/dev/sd",                  # overwrite block devices
    r"dd\s+.*of=/dev/",             # dd to block devices
    r"chmod\s+-R\s+777\s+/(?!\S)",  # chmod -R 777 /
    r"curl.*\|\s*(?:ba)?sh",        # curl | sh (pipe to shell)
    r"wget.*\|\s*(?:ba)?sh",        # wget | sh
]
```

**What this does NOT block:**
- `rm -rf ./node_modules` — legitimate cleanup, relative path
- `del /s /q .\build` — legitimate cleanup, relative path  
- Normal `npm`, `npx`, `pip`, `python` commands

**Additional enforcement:**
- Validate that the Popen `cwd` resolves inside `BASE_WORKSPACE_DIR` (currently it uses `self.workspace_path` which comes from the request, but the request validation in the router already checks this — adding a redundant check at the tool level for defense-in-depth)

---

### Syntax Validation Integration

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

Integrate `syntax_guard.validate_file_content()` into every tool that modifies files:

**`WriteFileTool.run()`** — validate `content` before writing:
```python
from syntax_guard import validate_file_content

def run(self, file_path: str, content: str) -> str:
    # ... existing approval check ...
    # ... existing path validation ...
    
    # NEW: Syntax validation before write
    error = validate_file_content(file_path, content)
    if error:
        return error
    
    # ... existing write logic ...
```

**`ReplaceInFileTool.run()`** — validate the *resulting* content before writing:
```python
def run(self, file_path: str, old_text: str, new_text: str) -> str:
    # ... existing logic up to building new_content ...
    new_content = content.replace(old_text, new_text, 1)
    
    # NEW: Validate before committing
    error = validate_file_content(file_path, new_content)
    if error:
        return error
    
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(new_content)
```

**`EditFileLinesTool.run()` and `InsertAtLineTool.run()`** — same pattern: build the result in memory, validate, then write.

---

### Batch Edit Tool (New)

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

Add `BatchReplaceFileContentTool` — atomic multi-edit in a single transaction:

```python
class ReplacementChunk(BaseModel):
    start_line: int = Field(description="1-based start line of the range containing target_content.")
    end_line: int = Field(description="1-based end line (inclusive) of the range.")
    target_content: str = Field(description="Exact text to find within the line range.")
    replacement_content: str = Field(description="Text to replace target_content with.")

class BatchReplaceFileContentSchema(BaseModel):
    file_path: str = Field(description="Relative path to the file to edit.")
    chunks: list[ReplacementChunk] = Field(description="List of replacement operations to apply atomically.")

class BatchReplaceFileContentTool:
    name = "batch_replace_file_content"
    description = (
        "Apply multiple non-contiguous edits to a single file in one atomic transaction. "
        "All edits are validated before any are applied. If any edit fails validation "
        "(target_content not found in range, or resulting syntax is invalid), "
        "the entire operation is rolled back.\n"
        "Chunks are applied bottom-to-top to preserve line numbers."
    )
    args_schema = BatchReplaceFileContentSchema
```

**Transaction logic:**
1. Read file content
2. Sort chunks by `start_line` descending (bottom-to-top)
3. For each chunk: verify `target_content` exists exactly once in the specified line range
4. If any verification fails → abort with detailed error, write nothing
5. Apply all replacements (bottom-to-top preserves line numbers)
6. Run `validate_file_content()` on the final result
7. If validation fails → abort, write nothing
8. Write to disk

---

### Concurrent Edit Protection

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

Add a module-level per-file lock registry to prevent race conditions when the LLM fires parallel tool calls on the same file:

```python
import threading
from collections import defaultdict

_file_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

def _get_file_lock(file_path: str) -> threading.Lock:
    """Get or create a lock for a specific file path."""
    return _file_locks[os.path.abspath(file_path)]
```

Every file-modifying tool (`WriteFileTool`, `ReplaceInFileTool`, `EditFileLinesTool`, `InsertAtLineTool`, `BatchReplaceFileContentTool`) acquires the lock before reading+writing:

```python
def run(self, file_path: str, content: str) -> str:
    # ... path validation ...
    with _get_file_lock(target_path):
        # ... read, validate, write ...
```

---

### Run Lifecycle Integration

#### [MODIFY] [agent_loop.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/agent_loop.py)

Reset the syntax guard failure counters at the start of each run:

```diff
+from syntax_guard import reset_failure_counts

 def run_agent_loop(...):
+    reset_failure_counts()
     messages = [...]
     # ... rest of loop ...
```

---

### Registry Update

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

Add `BatchReplaceFileContentTool` to `create_dev_tool_registry()`:

```diff
 def create_dev_tool_registry(...) -> ToolRegistry:
     tools = [
         # ... existing tools ...
+        BatchReplaceFileContentTool(
+            workspace_path=workspace_path,
+            require_approval=require_approval,
+            approval_callback=approval_callback,
+        ),
         ReportTaskStatusTool(result_holder=task_status),
     ]
```

---

## Files Changed Summary

| File | Action | What |
|------|--------|------|
| [syntax_guard.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/syntax_guard.py) | **NEW** | Validation module: AST, JSON, size limits, retry budget |
| [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py) | **MODIFY** | Add command blocklist, syntax validation calls, file locks, batch edit tool |
| [agent_loop.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/agent_loop.py) | **MODIFY** | Reset failure counters at run start |

---

## Verification Plan

### Automated Tests

Create [tests/test_syntax_guard.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/tests/test_syntax_guard.py):

1. **Python validation**: Valid `.py` → passes, broken `.py` → returns error with line number
2. **JSON validation**: Valid `.json` → passes, broken `.json` → returns error
3. **Non-validated extensions**: `.js`, `.tsx`, `.css` → always passes (no validation)
4. **File size cap**: Content > 2MB → rejected
5. **Retry budget**: 3 failures → subsequent attempts blocked, `reset_failure_counts()` clears it
6. **Command blocklist**: `rm -rf /` → blocked, `rm -rf ./node_modules` → allowed
7. **Batch edit**: Multi-chunk bottom-to-top application preserves line numbers
8. **Batch transaction**: One bad chunk → entire operation aborted, file unchanged

```bash
cd backend && python -m pytest tests/test_syntax_guard.py -v
```

### Integration Smoke Test

```bash
cd backend && python -c "from dev_tools import create_dev_tool_registry; print('Registry OK')"
cd backend && python -c "from syntax_guard import validate_file_content; print(validate_file_content('test.py', 'def foo(:\n  pass'))"
```

### Manual Verification

- Run a full develop cycle and confirm:
  - Agent can still write valid Python/JSON files normally
  - Agent gets a clear rejection if it produces broken Python syntax
  - Terminal commands like `npm install` still work
  - Dangerous commands are blocked with a clear message
