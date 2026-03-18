import os
import sys
from dotenv import load_dotenv

load_dotenv("../.env")

import litellm
import json
from crewai import Agent, Task, Crew, LLM

old_completion = litellm.completion
real_stdout = sys.stdout

def custom_patched_completion(*args, **kwargs):
    # Force streaming!
    kwargs['stream'] = True
    
    response_generator = old_completion(*args, **kwargs)
    
    full_content = ""
    full_reasoning = ""
    
    # Iterate through the chunks live!
    for chunk in response_generator:
        try:
            delta = chunk.choices[0].delta
            
            # Extract reasoning
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                full_reasoning += delta.reasoning_content
                real_stdout.write(f"\n[LIVE THINK] {delta.reasoning_content}")
                real_stdout.flush()
                
            # Extract actual content
            if hasattr(delta, "content") and delta.content:
                full_content += delta.content
        except Exception as e:
            real_stdout.write(f"\n[ERROR] {e}")
            pass
            
    # Now we need to construct a synchronous response object to return to CrewAI
    # LiteLLM's ModelResponse
    from litellm.utils import ModelResponse, Choices, Message
    
    msg = Message(content=full_content, role="assistant")
    if hasattr(msg, "reasoning_content"):
        msg.reasoning_content = full_reasoning
        
    choice = Choices(message=msg, finish_reason="stop", index=0)
    
    sync_resp = ModelResponse(
        choices=[choice],
        model=kwargs.get("model", "gemini"),
        usage={} # mock usage
    )
    
    return sync_resp

litellm.completion = custom_patched_completion

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
    task = Task(description="Solve 25 * 48. Think step by step.", expected_output="number", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    
    print("Kicking off crew...")
    crew.kickoff()
finally:
    print("Done testing.")
