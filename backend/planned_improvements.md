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

## 3. Headless Browser Verification
*Status: Proposed*

Provide the agent with visual capabilities to verify client-side layouts and catch browser-level exceptions.

### Proposed Upgrades:
1.  **📸 `take_browser_screenshot(url, output_filename)`**:
    *   Uses headless Playwright/Puppeteer to load local servers (e.g. `localhost:8080`) and capture high-resolution images of viewports, allowing the agent to inspect the visual rendering of its work.
2.  **📋 `harvest_browser_logs(url, wait_seconds)`**:
    *   Opens a page for 3 seconds and collects console errors (`console.error`, uncaught Javascript Exceptions, and resource 404s), feeding them back to the agent so it can self-repair broken client-side imports.
3.  **Connection Warmup**:
    *   Ensure the tool pings the local port first to wait for the local development server (like `npm run dev`) to fully boot before opening the browser.

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



