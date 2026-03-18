import os
import sys
from dotenv import load_dotenv

load_dotenv("../.env")

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
