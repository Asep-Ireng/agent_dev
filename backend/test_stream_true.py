import os
import sys
from dotenv import load_dotenv

load_dotenv("../.env")

import litellm
from crewai import Agent, Task, Crew, LLM

old_completion = litellm.completion

# Let's see if stream=True is even passed!
def patched_completion(*args, **kwargs):
    print(f"[LITELLM KWARGS] stream={kwargs.get('stream')} reasoning={kwargs.get('reasoning_effort')}")
    response = old_completion(*args, **kwargs)
    if kwargs.get("stream"):
        def wrapper():
            for chunk in response:
                try:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        sys.stdout.write(f"\n[PATCH THINKING] {delta.reasoning_content}")
                        sys.stdout.flush()
                except Exception:
                    pass
                yield chunk
        return wrapper()
    else:
        # if not streaming, let's see if reasoning_content is in the full response
        pass
    return response

litellm.completion = patched_completion

try:
    llm = LLM(
        model="gemini/gemini-2.5-pro",
        reasoning_effort="high"
    )
    agent = Agent(
        role="Mathematician",
        goal="Solve math problems",
        backstory="You are a genius.",
        verbose=True,
        allow_delegation=False,
        llm=llm
        # Note: I didn't pass stream=True here, let's see what happens.
    )
    task = Task(description="Solve 25 * 48. Think step by step.", expected_output="number", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    crew.kickoff()
finally:
    print("Done testing.")
