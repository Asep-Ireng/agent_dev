import os
import sys
import pprint
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from crewai import Agent, Task, Crew, LLM

def main():
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
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )

    task = Task(description="Calculate 25 * 48. Return only the number.", expected_output="number", agent=agent)
    crew = Crew(agents=[agent], tasks=[task], stream=True)
    
    print("--- START STREAM ---")
    streaming_output = crew.kickoff()
    
    last_chunk = None
    all_chunks = []
    
    for i, chunk in enumerate(streaming_output):
        all_chunks.append(chunk)
        last_chunk = chunk
        chunk_type = getattr(chunk, "chunk_type", "UNKNOWN")
        content = getattr(chunk, "content", "N/A")
        print(f"CHUNK {i} - Type: {chunk_type} - Content: {repr(content)[:100]}")
    
    print("\n--- STREAM FINISHED ---")
    
    print("\nLAST CHUNK ATTRIBUTES:")
    print("-" * 40)
    for attr in dir(last_chunk):
        if not attr.startswith('_'):
            try:
                val = getattr(last_chunk, attr)
                # Don't print methods
                if not callable(val):
                    print(f"  {attr}: {type(val).__name__} = {repr(val)[:200]}")
            except Exception as e:
                print(f"  {attr}: <Error getting value: {e}>")
                
    print("\nCREW OBJECT ATTRIBUTES AFTER STREAM:")
    print("-" * 40)
    # Check what fields are actually on the Crew object now
    for attr in dir(crew):
        if not attr.startswith('_') and not callable(getattr(crew, attr, None)):
            pass # skip for now to keep output clean, but we can check if needed
            
    # Try accessing standard Crew final output fields
    if hasattr(crew, 'tasks_output'):
        print(f"crew.tasks_output exists. Length: {len(crew.tasks_output)}")
        if crew.tasks_output:
            print(f"First task raw output: {crew.tasks_output[0].raw}")

if __name__ == "__main__":
    main()
