import os
import sys
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

import litellm

litellm.set_verbose = False

try:
    model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
    if not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"

    response = litellm.completion(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model=model_name,
        messages=[{"role": "user", "content": "What is 25 * 48? Explain step by step."}],
        stream=True,
        reasoning_effort="high"
    )
    for i, chunk in enumerate(response):
        c_dict = chunk.model_dump()
        delta = c_dict.get("choices", [{}])[0].get("delta", {})
        print(f"Chunk {i}: {delta}")
        if i > 10: break
except Exception as e:
    print(f"Error: {e}")
