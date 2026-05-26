"""
routers/design.py — POST /api/design/chat endpoint.
"""

import os
import io
import base64
import traceback
import json as _json
import yaml

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.exceptions import HTTPException
from typing import List
from PyPDF2 import PdfReader
import litellm

from helpers import get_current_provider, get_current_model, get_litellm_model, set_keys_from_env
from design_tools import UpdateSpecTool

router = APIRouter()


@router.post("/api/design/chat")
async def generate_design_chat(
    idea: str = Form(...), spec: str = Form(""), files: List[UploadFile] = File(None)
):
    try:
        set_keys_from_env()
        provider = get_current_provider()
        model = get_current_model()
        model_str = get_litellm_model(model, provider)

        # 1. Process Uploaded Files
        file_context = ""
        image_urls = []

        if files:
            for file in files:
                contents = await file.read()

                # Extract PDF text
                if file.filename.lower().endswith(".pdf"):
                    pdf_reader = PdfReader(io.BytesIO(contents))
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    file_context += (
                        f"\n--- PDF Extracted Content: {file.filename} ---\n{text}\n"
                    )

                # Encode Images to Base64
                elif file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    base64_image = base64.b64encode(contents).decode("utf-8")
                    mime_type = file.content_type
                    data_url = f"data:{mime_type};base64,{base64_image}"
                    image_urls.append(data_url)
                    file_context += (
                        f"\n--- Image Uploaded: {file.filename} (passed natively) ---\n"
                    )

        # 2. Build the Prompt Context
        context_prompt = f"User Request / Idea: {idea}\n\n"
        if spec:
            context_prompt += f"CURRENT SPECIFICATION (Edit this based on the user's new request):\n{spec}\n\n"
        if file_context:
            context_prompt += f"ATTACHED FILE CONTEXT:\n{file_context}\n\n"

        # 3. Load agent config and build system prompt
        with open(os.path.join(os.path.dirname(__file__), "..", "config", "agents.yaml"), "r", encoding="utf-8") as f:
            agents_config = yaml.safe_load(f)

        system_prompt = (
            f"You are a {agents_config['designer']['role']}.\n\n"
            f"Your goal: {agents_config['designer']['goal']}\n\n"
            f"Background: {agents_config['designer']['backstory']}"
        )

        # 4. Set up UpdateSpecTool with shared result holder
        spec_result = {}
        update_spec_tool = UpdateSpecTool(result_holder=spec_result)

        # 5. Build user message (may include images)
        user_content: list = [{"type": "text", "text": context_prompt}]
        for data_url in image_urls:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": data_url},
            })
        user_msg = user_content if len(user_content) > 1 else context_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        # 6. Single-turn call with function calling (not a loop — design is one-shot)
        response = litellm.completion(
            model=model_str,
            messages=messages,
            tools=[update_spec_tool.to_openai_schema()],
            tool_choice="auto",
        )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        # 7. Extract result from tool call or raw text
        choice = response.choices[0]
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                if tc.function.name == "update_specification":
                    try:
                        args = _json.loads(tc.function.arguments)
                        update_spec_tool.run(
                            updated_spec=args.get("updated_spec", ""),
                            change_summary=args.get("change_summary", ""),
                        )
                    except Exception:
                        pass

        if spec_result.get("spec"):
            return {
                "spec": spec_result["spec"],
                "summary": spec_result.get("summary", "Specification updated."),
                "usage": usage,
            }
        else:
            raw_output = choice.message.content or ""
            return {
                "spec": raw_output,
                "summary": "Specification generated.",
                "usage": usage,
            }

    except Exception as e:
        print(f"Server Error during Design Chat: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during design generation.",
        )
