import litellm
import os
import sys
import json

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

try:
    model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
    if not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"

    response = litellm.completion(
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        model=model_name,
        messages=[{"role": "user", "content": "Solve: 25 * 48. Think step by step."}],
        stream=True,
        reasoning_effort="high"
    )
    for i, chunk in enumerate(response):
        print(chunk.model_dump())
        if i > 5: break
except Exception as e:
    print(e)
