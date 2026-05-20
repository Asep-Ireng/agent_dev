import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from crewai import Agent, Task, Crew, LLM

try:
    model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
    if not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"

    llm = LLM(
        model=model_name,
        reasoning_effort="low",
        api_key=os.getenv("GOOGLE_API_KEY"),
    )
    agent = Agent(
        role="Mathematician",
        goal="Solve math problems",
        backstory="You are a genius.",
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )
    task = Task(description="Solve 25 * 48. Think step by step.", expected_output="number", agent=agent)
    crew = Crew(agents=[agent], tasks=[task], stream=True)

    streaming_output = crew.kickoff()

    print("\n=== STREAMING OUTPUT ===")
    for chunk in streaming_output:
        print(f"[{chunk.chunk_type}] {chunk.content}", end="", flush=True)

finally:
    print("\nDone testing.")
