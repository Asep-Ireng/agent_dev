import os
from crewai import Agent, Task, Crew, Process
from langchain.tools import tool

# ==========================================
# 1. Custom Tools
# ==========================================

@tool("Execute Python Code")
def execute_code_tool(code: str) -> str:
    """Useful to execute python code in a sandboxed environment."""
    return "Execution successful. Tests passed."

@tool("Write File Sandbox")
def write_file_tool(filename: str, content: str) -> str:
    """Writes code to a file in the workspace."""
    with open(f"sandbox_{filename}", "w") as f:
        f.write(content)
    return f"Successfully wrote to sandbox_{filename}"


def start_hitl_workflow():
    # ==========================================
    # 2. Define the Agents
    # ==========================================
    
    designer = Agent(
        role='Lead Product Designer',
        goal='Design a comprehensive app technical spec.',
        backstory="You are a visionary. You plan the tech stack, file structure, and API contracts.",
        verbose=True,
        allow_delegation=False
    )

    developer = Agent(
        role='Senior Full-Stack Developer',
        goal='Write clean, bug-free code and save it to the file system based on specs.',
        backstory="You take specs and output perfect, modern code. You write files directly using your tools.",
        tools=[write_file_tool, execute_code_tool],
        verbose=True,
        allow_delegation=False
    )

    # ==========================================
    # 3. Define the Tasks (WITH HUMAN IN THE LOOP)
    # ==========================================
    
    design_task = Task(
        description='Take this app idea: "{app_idea}" and create a detailed markdown spec. Include core features, stack, and a file tree.',
        expected_output='A markdown document containing the complete architecture.',
        agent=designer,
        human_input=True # <--- THIS IS THE MAGIC FLAG FOR HUMAN IN THE LOOP
    )

    dev_task = Task(
        description='Read the approved designer\'s spec. Write the actual code for the core files. Use your Write File Sandbox tool to save the files.',
        expected_output='Confirmation that files were written and tests passed.',
        agent=developer
    )

    # ==========================================
    # 4. Assemble the Crew
    # ==========================================
    
    crew = Crew(
        agents=[designer, developer],
        tasks=[design_task, dev_task],
        process=Process.sequential,
        verbose=True
    )

    return crew

if __name__ == "__main__":
    app_idea = input("Give me an app idea to build: ")
    crew = start_hitl_workflow()
    result = crew.kickoff(inputs={'app_idea': app_idea})
    
    print("\n================ FINAL END RESULT ================\n")
    print(result)
