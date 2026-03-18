import os
import sys
import json
from dotenv import load_dotenv

load_dotenv("../.env")

import litellm

litellm.set_verbose = False

try:
    response = litellm.completion(
        model="gemini/gemini-2.5-pro", # Using this as standard to test Litellm's reasoning structure
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
