import litellm
import os
import sys
import json

from dotenv import load_dotenv
load_dotenv("../.env")

try:
    response = litellm.completion(
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        model="gemini/gemini-2.5-pro",
        messages=[{"role": "user", "content": "Solve: 25 * 48. Think step by step."}],
        stream=True,
        reasoning_effort="high"
    )
    for i, chunk in enumerate(response):
        print(chunk.model_dump())
        if i > 5: break
except Exception as e:
    print(e)
