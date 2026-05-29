"""
syntax_guard.py — Content validation engine for the dev-agent tool suite.

Responsibilities:
  - AST syntax validation for .py files (ast.parse)
  - Syntax validation for .json files (json.loads)
  - File-size cap enforcement (2 MB)
  - Per-invocation failure-budget tracking (3 strikes → halt writes)

Design notes:
  - Non-.py / non-.json extensions always pass — no false positives on JS/TS/CSS/HTML.
  - The failure counter is module-level and process-scoped (single-process uvicorn assumption).
  - Call reset_failure_counts() at the start of each agent invocation.
"""

import ast
import json
import threading

# ---------------------------------------------------------------------------
# Module-level state (process-scoped, single-worker assumption)
# ---------------------------------------------------------------------------

_failure_count: int = 0
_lock: threading.Lock = threading.Lock()

MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024  # 2 MB
MAX_FAILURES_PER_RUN: int = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_content(file_path: str, content: str) -> tuple[bool, str]:
    """Validate content before writing to disk.

    Routes to the appropriate validator based on file extension.
    Non-.py / non-.json files always return (True, "").

    Args:
        file_path: Relative or absolute path — only the extension is used.
        content:   The string content about to be written.

    Returns:
        (True, "")              — content is safe to write
        (False, error_message)  — content has a syntax problem
    """
    ext = _extension(file_path)

    if ext == ".py":
        return _validate_python(content)
    if ext == ".json":
        return _validate_json(content)

    # All other extensions (JS, TS, TSX, CSS, HTML, MD, …) — passthrough.
    return True, ""


def validate_file_size(content: str) -> tuple[bool, str]:
    """Reject content that exceeds the 2 MB hard cap.

    Args:
        content: The string content about to be written.

    Returns:
        (True, "")              — size is within limits
        (False, error_message)  — content is too large
    """
    size = len(content.encode("utf-8"))
    if size > MAX_FILE_SIZE_BYTES:
        return (
            False,
            f"Content too large: {size:,} bytes exceeds the {MAX_FILE_SIZE_BYTES:,}-byte (2 MB) limit.",
        )
    return True, ""


def increment_failure() -> bool:
    """Bump the failure counter and report whether the budget is exhausted.

    Thread-safe.

    Returns:
        True  — budget is now exhausted (>= MAX_FAILURES_PER_RUN); caller must halt.
        False — still within budget; caller may continue with a warning.
    """
    global _failure_count
    with _lock:
        _failure_count += 1
        return _failure_count >= MAX_FAILURES_PER_RUN


def reset_failure_counts() -> None:
    """Reset the failure counter to 0.

    Call this at the very start of each agent-loop invocation so the budget
    is per-task, not sticky across multiple runs.
    """
    global _failure_count
    with _lock:
        _failure_count = 0


def get_failure_count() -> int:
    """Return the current failure count (for logging/diagnostics)."""
    with _lock:
        return _failure_count


# ---------------------------------------------------------------------------
# Internal validators
# ---------------------------------------------------------------------------


def _validate_python(content: str) -> tuple[bool, str]:
    """Run ast.parse on content; return (False, err) on SyntaxError."""
    try:
        ast.parse(content)
        return True, ""
    except SyntaxError as exc:
        return (
            False,
            f"Python SyntaxError at line {exc.lineno}: {exc.msg}",
        )
    except Exception as exc:  # pragma: no cover — unexpected parse errors
        return False, f"Python parse error: {exc}"


def _validate_json(content: str) -> tuple[bool, str]:
    """Run json.loads on content; return (False, err) on JSONDecodeError."""
    try:
        json.loads(content)
        return True, ""
    except json.JSONDecodeError as exc:
        return (
            False,
            f"JSON error at line {exc.lineno} col {exc.colno}: {exc.msg}",
        )
    except Exception as exc:  # pragma: no cover
        return False, f"JSON parse error: {exc}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extension(file_path: str) -> str:
    """Extract the lowercase file extension including the leading dot."""
    import os

    _, ext = os.path.splitext(file_path)
    return ext.lower()
