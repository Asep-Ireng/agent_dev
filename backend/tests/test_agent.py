import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from crewai import Agent, Task, Crew, LLM

old_stdout = sys.stdout

class Catch:
    def write(self, text):
        if text.strip():
            old_stdout.write(f"[CATCHED] {text!r}\n")
            old_stdout.flush()
    
    def flush(self):
        old_stdout.flush()

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

    task = Task(
        description="Solve 25 * 48. Think step by step.",
        expected_output="the numeric answer",
        agent=agent
    )

    crew = Crew(agents=[agent], tasks=[task])
    crew.kickoff()
finally:
    sys.stdout = old_stdout
    print("Done testing.")
