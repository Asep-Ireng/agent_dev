# Planned Improvements Roadmap — Agentic Dev Platform

This document consolidates all completed upgrades, active plans, and future conceptual roadmaps for the `agent_dev` platform. 

---

## 1. Developer Tools Safety Hardening (Option A)
---

## 2. Hybrid Web Search Tool
*Status: Ready to Execute*

Give the developer agent the ability to query the web for API documentation, library features, and compile-error troubleshooting.

### Proposed Upgrades:
1.  **Standard WebSearchTool**:
    *   Provide a Pydantic tool schema `web_search(query: str, max_results: int)`.
2.  **Hybrid Resolution Flow**:
    *   **API-First**: Check `.env` for keys like `TAVILY_API_KEY` or `SERPER_API_KEY`. If present, query the official search API for clean markdown summaries.
    *   **Scraper Fallback**: If no key is configured, fallback to parsing DuckDuckGo's raw HTML interface (`https://duckduckgo.com/html/`) using `requests` and `BeautifulSoup` to return search links and snippets.

---

## 3. Headless Browser Verification (Two-Tier)
*Status: Proposed*

Provide the agent with visual capabilities to verify client-side layouts and catch browser-level exceptions. Uses a **two-tier** architecture — lightweight checks via **Alumnium** and deep agentic verification via **Browser Use**.

### Tier 1: Basic Checks — Alumnium (`pip install alumnium`)

Alumnium is an AI-native wrapper over Selenium/Playwright that translates natural-language instructions into browser actions via `al.do()`, `al.check()`, and `al.get()`. Fast, low-overhead, ideal for deterministic checks the agent runs after every build.

1.  **📸 `take_browser_screenshot(url, output_filename)`**:
    *   Spins up a headless Playwright driver via Alumnium, loads `localhost` URLs, captures high-resolution viewport screenshots.
    *   Returns the image as base64 for the next LLM turn (if the model supports vision), or saves to workspace.
2.  **📋 `harvest_browser_logs(url, wait_seconds)`**:
    *   Opens a page for a configurable duration and collects `console.error`, uncaught JS exceptions, and resource 404s.
    *   Feeds structured error lists back to the agent so it can self-repair broken imports or runtime crashes.
3.  **✅ `check_page_element(url, assertion)`**:
    *   Uses `al.check("...")` to verify natural-language assertions about the page state (e.g. `"page title contains Dashboard"`, `"login button is visible"`).
    *   Returns pass/fail + page context on failure.

### Tier 2: Detailed Verification — Browser Use (`pip install browser-use`)

Browser Use is a full agentic browser automation framework — it gives the LLM direct control of a Playwright browser to perform complex multi-step UI verification flows autonomously.

1.  **🔍 `deep_browser_verify(url, task_description)`**:
    *   Spawns a Browser Use `Agent` with a verification task (e.g. `"Navigate to /dashboard, click 'Add Item', fill in the form, submit, and verify the item appears in the list"`).
    *   The agent reasons about the page DOM/visual state and executes clicks, typing, navigation, and assertions autonomously.
    *   Returns a structured verification report: steps taken, screenshots at key points, pass/fail status, and any errors encountered.
2.  **🎨 `visual_regression_check(url, reference_screenshot)`**:
    *   Uses Browser Use to load the page, capture the current state, and compare against a reference screenshot.
    *   Reports visual differences with annotated regions and confidence scores.
3.  **🐛 `interactive_debug_session(url, bug_description)`**:
    *   Gives the agent a browser instance to freely explore and reproduce a reported bug.
    *   Returns reproduction steps, console errors, network failures, and suggested fixes.

### Shared Infrastructure:

1.  **Connection Warmup**:
    *   Both tiers ping the local port first (max 30s timeout with health-check polling) to wait for the dev server (`npm run dev`, `python -m http.server`, etc.) to fully boot before opening the browser.
2.  **Origin Restriction**:
    *   All browser tools are restricted to `localhost` / `127.0.0.1` origins by default to prevent the agent from browsing arbitrary external URLs.
3.  **Optional Dependencies**:
    *   Both `alumnium` and `browser-use` are optional installs — not hard requirements. Add as extras group: `pip install .[browser]`.
    *   Playwright browser binaries (~200MB) installed on first use via `playwright install chromium`.

---

## 4. Frontend Chat Retry Mechanism
*Status: Proposed*

Recover gracefully from backend timeouts, model reasoning freezes, or API connection errors.

### Proposed Upgrades:
1.  **↺ Retry Prompt Button**:
    *   If the SSE stream closes with an error, or if the assistant response container is empty on execution end, display a subtle `↺ Retry Prompt` action link directly under the user's sent bubble.
2.  **State Preservation**:
    *   Clicking retry grabs the last user prompt and re-triggers the design or develop submit handler programmatically.
3.  **Endpoint Health Check**:
    *   Expose `GET /api/health` in the backend. If the backend server goes offline, display a visual indicator banner instead of failing silently.

---

## 5. Dynamic Tool Self-Assembly Spec (LATM)
*Status: Academic Concept (Skripsi/Tugas Akhir Blueprint)*

A research-grade architecture exploring how the agent can programmatically write and register its own tools at runtime.

### Proposed Upgrades:
1.  **`create_custom_tool` Tool**:
    *   Allows the developer agent to send name, description, schema definitions, and raw Python code to build a new tool.
2.  **Two-Tier Wallet Safeguards**:
    *   *Tier 1 (Budget Consent)*: Agent asks the user if it's okay to spawn the Tool-Maker debate loop (estimating API costs) before executing anything.
    *   *Tier 2 (Code Approval)*: User reviews the generated schema, unit tests, and code inside a side-by-side comparison drawer before registering it.
3.  **Multi-Model Consensus & Debate (MoA)**:
    *   Run parallel Tool Maker agent instances on Claude Sonnet (algorithm optimization) and GPT-4o (OOP typing).
    *   Let the models cross-critique each other's code to filter boundary errors before presentment.
4.  **Academic Study (LATM vs. In-Workspace Scripting)**:
    *   *Thesis Question*: Compare the git portability, reusability, and execution security of registry-level Dynamic Tools against local project script generation.

---

## 6. Direct Developer Chat Access (Existing Project Mode)
*Status: Ready to Execute*

Bypasses the "Architecture Planning" phase for pre-existing codebases, allowing the user to connect directly to an existing folder and start applying changes or asking questions.

### Proposed Upgrades:
1.  **Sidebar Workspace Connector**:
    *   Add an `📂 Open Codebase` button directly below the Workspace Path input field in `Sidebar.tsx`.
2.  **Frontend State Bypass**:
    *   When clicked, trigger `onOpenExistingCodebase()` to set `agentResult` directly to a placeholder state: `"Connected to workspace. Direct developer session active."`
    *   Initialize `devChatMessages` with a system greeting instruction: *"Connected. What would you like to build, change, or debug in this folder?"*
    *   This instantly renders the `DevChat` iteration component at the bottom of the interface, bypassing the initial design generation step completely.
3.  **Unified Iterate Route Safety**:
    *   Confirm that the backend `/api/dev-iterate` endpoint resolves correctly when both `spec` and `dev_context` are empty. 
    *   (Checked: The backend already compiles the user's instructions cleanly using fallback context headers when they are blank).

---

## 7. Dev Chat Tool Access Toggle (Ask & Apply)
*Status: Ready to Execute*

Introduce a toggle switch in the Dev Chat panel ("Use Tools") that is active in both "Ask" and "Apply" modes. This allows the user to disable tool access during interactive chat sessions.

### Proposed Upgrades:

1.  **Dev Chat Endpoint Update (`/api/dev-chat`)**:
    *   Add `enable_tools: bool = Form(True)` in `backend/routers/dev_chat.py`.
    *   If `enable_tools` is false, run a single-turn `litellm.completion` call without passing `tools`/`tool_choice` to skip the tool-resolution loop.
2.  **Iterate Endpoint Update (`/api/dev-iterate`)**:
    *   Add `enable_tools: bool = True` to the `IterateRequest` model in `config.py`.
    *   In `/api/dev-iterate` (`backend/routers/iterate.py`), check `req.enable_tools`. If false, instantiate the agent with an empty `ToolRegistry([])` so it only writes text.
3.  **Frontend State & Toggle**:
    *   Define `enableAgentTools` and `setEnableAgentTools` states in `page.tsx` (defaulting to `true`).
    *   Pass them to `DevChat.tsx`.
    *   In `DevChat.tsx`, render a small toggle switch labeled "Use Tools" next to the mode picker.
    *   Pass the toggle state in `handleDevChat` (via Form Data `enable_tools`) and in `handleApplyProceed` (via JSON body `enable_tools`).

---

## 8. Autonomous Image & Asset Generator Tool
*Status: Proposed*

Provide the developer agent with an image generation tool so it can autonomously generate visual assets, icons, or mock illustrations for the frontend instead of using placeholder boxes or broken local image paths.

### Proposed Upgrades:

1.  **`GenerateAssetTool` Schema**:
    *   Register `generate_asset(prompt: str, filename: str = "mock_asset.png", resolution: str = "1024x1024")` in `backend/dev_tools.py`.
2.  **API Integration (Nano Banana / Gemini Imagen API)**:
    *   Use the Gemini API / Google AI Studio Imagen models (or a configured endpoint like `imagen-3.0-generate-002`) to request text-to-image generations using the specified prompt.
    *   Save the resulting bytes as a file under the workspace path (e.g. `workspace/public/images/{filename}`) so it immediately links into the code cleanly.
3.  **Sandboxing & Path Safety**:
    *   Sanitize the target path to ensure generated files are strictly saved within the active workspace bounds.

---

## 9. Document Export Toolkit (PDF / Word / Excel)
*Status: Proposed*

Give the design agent (and optionally the dev agent) tools to export specs, reports, and structured data into professional document formats — PDF, Word (.docx), and Excel (.xlsx) — using Python libraries.

### Proposed Tools:

1.  **📄 `export_html_to_pdf(html_content, filename, css)`**:
    *   Renders HTML + CSS to a polished PDF using **WeasyPrint** (`pip install weasyprint`) or **pdfkit** (wkhtmltopdf wrapper).
    *   WeasyPrint is preferred (pure Python, no external binary dependency) — pdfkit as fallback if wkhtmltopdf is already installed.
    *   Supports Jinja2 templating: the agent can compose an HTML template string with dynamic data, then export.
    *   Output saved to workspace (e.g. `workspace/exports/{filename}.pdf`).

2.  **📝 `export_to_docx(title, sections, filename)`**:
    *   Uses **python-docx** (`pip install python-docx`) to build structured Word documents.
    *   `sections` parameter accepts a list of typed blocks:
        ```json
        [
          {"type": "heading", "level": 1, "text": "Architecture Spec"},
          {"type": "paragraph", "text": "This system uses..."},
          {"type": "table", "headers": ["Component", "Role"], "rows": [["API", "Backend"], ["UI", "Frontend"]]},
          {"type": "image", "path": "diagram.png", "width_inches": 5}
        ]
        ```
    *   Applies a clean default style (Calibri, proper heading hierarchy, table borders) — the agent doesn't need to micromanage formatting.

3.  **📊 `export_to_xlsx(sheets, filename)`**:
    *   Uses **openpyxl** (`pip install openpyxl`) to build multi-sheet Excel workbooks.
    *   `sheets` parameter accepts a list of sheet definitions:
        ```json
        [
          {
            "name": "API Endpoints",
            "headers": ["Route", "Method", "Description"],
            "rows": [["/api/develop", "POST", "Main build SSE stream"]],
            "auto_filter": true,
            "column_widths": [30, 10, 50]
          }
        ]
        ```
    *   Applies auto-sizing, header styling (bold + fill), and optional auto-filter for data tables.

4.  **📑 `export_markdown_to_pdf(markdown_content, filename)`**:
    *   Convenience wrapper: converts Markdown → HTML (via `markdown` or `markdown-it-py`) → PDF (via WeasyPrint).
    *   Useful for directly exporting the design spec or agent reports without the agent needing to write HTML.

### Integration Points:

*   **Design Agent**: Register tools in `design_tools.py` or a new `export_tools.py` module. The design agent can export the finalized spec to PDF/DOCX after the user approves it.
*   **Dev Agent**: Optionally available via `create_dev_tool_registry()` for agents that need to generate reports, data exports, or documentation as part of a build task.
*   **Dependencies**: All libraries (`weasyprint`, `python-docx`, `openpyxl`, `markdown`) added as optional extras: `pip install .[export]`.
*   **Path Safety**: All exports sandboxed to workspace bounds via `validate_workspace_path()`.
