import os
import sys
from dotenv import load_dotenv

load_dotenv("../.env")

import litellm
from litellm.integrations.custom_logger import CustomLogger
from crewai import Agent, Task, Crew, LLM

class MyLogger(CustomLogger):
    def log_stream_event(self, kwargs, response_obj, start_time, end_time):
        try:
            if hasattr(response_obj, "choices") and response_obj.choices:
                delta = response_obj.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    print(f"\n[MYLOGGER THINKING] {delta.reasoning_content}")
        except Exception:
            pass

old_stdout = sys.stdout
class Catch:
    def write(self, text):
        pass
    def flush(self):
        pass
sys.stdout = Catch()

try:
    llm = LLM(
        model="gemini/gemini-2.5-pro",
        reasoning_effort="high",
        callbacks=[MyLogger()]
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
    print("Done testing CustomLogger inside LLM.")
