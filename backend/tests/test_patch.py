import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

import litellm
from crewai import Agent, Task, Crew, LLM

old_completion = litellm.completion

def patched_completion(*args, **kwargs):
    response = old_completion(*args, **kwargs)
    if kwargs.get("stream"):
        def wrapper():
            for chunk in response:
                # check if there's reasoning
                try:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        # Write directly to original stdout since we capture print later
                        print(f"\n[PATCH THINKING] {delta.reasoning_content}")
                except Exception:
                    pass
                yield chunk
        return wrapper()
    return response

litellm.completion = patched_completion

# Now run crewai
old_stdout = sys.stdout

class Catch:
    def write(self, text):
        pass
    def flush(self):
        pass

sys.stdout = Catch()

try:
    model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
    if not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"

    llm = LLM(
        model=model_name,
        reasoning_effort="high",
        api_key=os.getenv("GOOGLE_API_KEY"),
    )
    agent = Agent(
        role="Mathematician",
        goal="Solve math problems",
        backstory="You are a genius.",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    task = Task(description="Solve 25 * 48. Think step by step.", expected_output="number", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    crew.kickoff()
finally:
    sys.stdout = old_stdout
    print("Done testing patch.")
