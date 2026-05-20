import os
import sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))
from crewai import Agent, Task, Crew, LLM

model_name = os.getenv("GOOGLE_MODEL", "gemini-3-flash-preview")
if not model_name.startswith("gemini/"):
    model_name = f"gemini/{model_name}"

llm = LLM(model=model_name, reasoning_effort='low', api_key=os.getenv('GOOGLE_API_KEY'))
agent = Agent(role='Math', goal='Math', backstory='genius', verbose=False, allow_delegation=False, llm=llm)
task = Task(description='What is 2+2?', expected_output='number', agent=agent)
crew = Crew(agents=[agent], tasks=[task], stream=True)
result = crew.kickoff()

print('type result:', type(result).__name__)
print('has raw on result obj:', hasattr(result, 'raw'))

last_chunk = None
all_types = []
for chunk in result:
    all_types.append(type(chunk).__name__)
    last_chunk = chunk

print('chunk types seen:', set(all_types))
if last_chunk:
    print('last chunk type:', type(last_chunk).__name__)
    print('last chunk fields:', [a for a in dir(last_chunk) if not a.startswith('_') and not callable(getattr(last_chunk, a, None))])

# Also try accessing raw on result after exhausting
print('raw on result after iter:', getattr(result, 'raw', 'N/A'))
