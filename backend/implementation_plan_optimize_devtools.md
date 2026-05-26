# Robust, Drift-Resistant File Editing Tools

Enhance the `agent_dev` tool suite (`backend/dev_tools.py`) with self-healing syntax guards and drift-resistant anchored editing to prevent AI agents from corrupting codebase files (such as missing class declarations, unbalanced braces, and stray lines).

## User Review Required

> [!IMPORTANT]
> **No Breaking Changes**: The existing tool names (`write_file`, `replace_in_file`, `edit_file_lines`, `insert_at_line`) are preserved exactly to maintain perfect compatibility with existing agent system prompts and backstories.
> We are extending the Pydantic schemas of these tools with **optional anchor/validation parameters** and adding a powerful new batch-editing tool (`batch_replace_file_content`).

> [!TIP]
> By incorporating transaction-style rollbacks on syntax failure (e.g., if a Python AST parse fails, we restore the original file and return a clear compiler error to the agent), we prevent the agent from saving broken files.

---

## Proposed Changes

### Tool System & AST Safeguards

We will add a new utility class/functions inside `backend/dev_tools.py` to handle syntax validation and file modification transactions.

#### [MODIFY] [dev_tools.py](file:///r:/Kuliah/Kuliah%20Rui/Project%20Gabut/agent_dev/backend/dev_tools.py)

We will implement:
1. **`validate_code_syntax(file_path: str, content: str) -> str | None`**:
   *   Checks syntax before saving.
   *   For `.py` files: Uses `ast.parse()`. If syntax is invalid, returns the traceback error.
   *   For `.json` files: Uses `json.loads()`. If invalid, returns the decoding error.
   *   For `.js`, `.ts`, `.tsx`, `.jsx`, `.html`, `.css`: Performs a fast bracket and quotes balance analysis (balancing `{}`, `[]`, `()`, `` ` ``). If unbalanced delimiters are detected, returns a warning detailing the mismatch (e.g., *"Unbalanced template literal backticks detected in Javascript module"*).
2. **`EditFileLinesSchema` & `InsertAtLineSchema` Schema Extension**:
   *   Add `anchor_content: str = ""` to `EditFileLinesSchema`. If provided, verifies that the lines to be replaced contain exactly this text before executing.
   *   Add `anchor_line_content: str = ""` to `InsertAtLineSchema`. If provided, verifies that the target insertion line contains exactly this text.
3. **`BatchReplaceFileContentTool` (`batch_replace_file_content`)** [NEW TOOL]:
   *   A new tool accepting:
     ```python
     class ReplacementChunk(BaseModel):
         start_line: int
         end_line: int
         target_content: str
         replacement_content: str
     ```
   *   Applies multiple edits to a single file in a single transaction.
   *   Sorts all chunks descending by `start_line` to avoid shifting line numbers of subsequent chunks (bottom-to-top application).
   *   Validates all chunks against their line range matches first. If any check fails, aborts the entire transaction with a detailed explanation.
   *   Runs `validate_code_syntax` on the resulting content before committing.

---

## Verification Plan

### Automated Tests
*   Verify that `python -c "import dev_tools; print('Imports OK')"` executes successfully without importing errors.
*   Write unit tests to verify:
    *   Syntactic validation successfully flags unbalanced backticks/braces in JS and invalid AST in Python.
    *   `batch_replace_file_content` successfully applies multiple non-contiguous edits bottom-to-top.
    *   Line-range edits with mismatched anchors fail gracefully without writing to the disk.

### Manual Verification
*   We will test editing a dummy Python/JS file with the newly upgraded tools and observe that incorrect line indices or bad syntax are rejected with explicit instructions.
