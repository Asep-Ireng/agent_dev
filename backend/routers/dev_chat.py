"""
routers/dev_chat.py — POST /api/dev-chat endpoint.
"""

import os
import base64
import traceback
from typing import List

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.exceptions import HTTPException
import litellm

from config import BASE_WORKSPACE_DIR
from helpers import (
    get_current_provider,
    get_current_model,
    get_litellm_model,
    set_keys_from_env,
    validate_workspace_path,
    validate_chat_history,
)

router = APIRouter()


@router.post("/api/dev-chat")
async def dev_chat(
    message: str = Form(...),
    spec: str = Form(""),
    workspace_path: str = Form(BASE_WORKSPACE_DIR),
    history: str = Form("[]"),  # JSON string of [{role, content}]
    files: List[UploadFile] = File(default=[]),
):
    """Chat with the dev agent about the code it built, with optional image attachments."""
    set_keys_from_env()
    provider = get_current_provider()
    model = get_current_model()

    try:
        # Validate inputs
        ws = validate_workspace_path(workspace_path)
        chat_history_raw = validate_chat_history(history)

        # Filter and cap history to prevent token explosion
        chat_history = []
        for msg in chat_history_raw:
            content = msg["content"]
            if (
                content.startswith("✅ **Changes Applied:**")
                or content.startswith("▶ Proceeding")
                or content.startswith("✕ Cancelled")
            ):
                continue
            if content.startswith("**📋 Proposed Plan:**"):
                content = content[:1000] + "\n\n... [Plan truncated for chat history brevity] ..."
            chat_history.append({"role": msg["role"], "content": content})

        # Only take the last 8 messages for context
        chat_history = chat_history[-8:]

        # Scan the workspace for a file tree to give the agent context
        file_tree = []
        if os.path.exists(ws):
            for root, dirs, files_list in os.walk(ws):
                dirs[:] = [
                    d
                    for d in dirs
                    if d
                    not in (
                        "node_modules",
                        ".git",
                        "__pycache__",
                        ".next",
                        "dist",
                        "build",
                        ".venv",
                        "venv",
                    )
                ]
                for fname in files_list:
                    rel = os.path.relpath(os.path.join(root, fname), ws)
                    file_tree.append(rel)

        tree_str = "\n".join(file_tree[:100])
        if len(file_tree) > 100:
            tree_str += f"\n... and {len(file_tree) - 100} more files"

        system_prompt = f"""You are the developer who just built an application. You built it according to this spec:

---
{spec}
---

The project is at: {ws}

File tree:
{tree_str}

You can discuss:
- Design decisions and why you made them
- Library choices and alternatives
- Code structure and architecture
- Bugs or issues the user points out
- Suggestions for improvements

If the user attaches screenshots, analyze what you see and provide specific feedback.
If the user asks about specific file contents, tell them which file to look at and what to expect there.
Keep responses concise and useful. Use markdown formatting."""

        messages = [{"role": "system", "content": system_prompt}]

        # Add validated chat history
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Build the current user message — may include images
        user_content = []
        user_content.append({"type": "text", "text": message})

        # Process uploaded images
        if files:
            for file in files:
                contents = await file.read()
                if file.filename and file.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp", ".gif")
                ):
                    b64 = base64.b64encode(contents).decode("utf-8")
                    mime = file.content_type or "image/png"
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        }
                    )

        # Use multimodal format if images are attached, plain text otherwise
        if len(user_content) == 1:
            messages.append({"role": "user", "content": message})
        else:
            messages.append({"role": "user", "content": user_content})

        model_str = get_litellm_model(model, provider)
        response = litellm.completion(model=model_str, messages=messages)

        reply = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        usage_dict = {}
        if usage:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }
        return {"reply": reply, "usage": usage_dict}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Server Error during Dev Chat: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred during dev chat."
        )
