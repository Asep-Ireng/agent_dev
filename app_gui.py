from logging import PlaceHolder
import os
import streamlit as st
from crewai import Agent, Task, Crew
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Prerequisites:
# pip install streamlit crewai langchain-openai
# To run: streamlit run app_gui.py

st.set_page_config(page_title="AI Dev Studio", layout="wide")

st.title("🚀 The 'I Hate Terminals' Agent Workflow")
st.markdown("Because sometimes the command line is just too dark and scary.")

# Initialize session state so we don't lose data when buttons are clicked
if "designer_output" not in st.session_state:
    st.session_state.designer_output = None
if "dev_output" not in st.session_state:
    st.session_state.dev_output = None

# ==========================================
# 1. Individual Agents & Crews
# (We break them up so Streamlit can pause for user input in between)
# ==========================================

def get_llm(model_name, provider):
    if provider == "Google (Gemini)":
        return f"gemini/{model_name}"
    return model_name

def run_designer(idea, model_name, provider):
    designer = Agent(
        role='Lead Product Designer',
        goal='Design a comprehensive app technical spec.',
        backstory="You are a visionary. You plan the tech stack, file structure, and UI/UX.",
        verbose=True,
        allow_delegation=False,
        llm=get_llm(model_name, provider)
    )
    design_task = Task(
        description=f'Take this app idea: "{idea}" and create a detailed markdown spec. Include core features, stack, and a file tree.',
        expected_output='Markdown document with architecture.', 
        agent=designer
    )
    crew = Crew(agents=[designer], tasks=[design_task])
    return crew.kickoff()


def run_developer(spec, model_name, provider):
    developer = Agent(
        role='Senior Full-Stack Developer',
        goal='Write clean code based on the designer spec.',
        backstory="You write perfect code and hate meetings. You only output code based on detailed specs.",
        verbose=True,
        allow_delegation=False,
        llm=get_llm(model_name, provider)
    )
    dev_task = Task(
        description=f'Read this approved spec and write the code for the core components:\n\n{spec}',
        expected_output='Working code blocks for the application.', 
        agent=developer
    )
    crew = Crew(agents=[developer], tasks=[dev_task])
    return crew.kickoff()

# ==========================================
# 2. The GUI Layout
# ==========================================

st.sidebar.header("Configuration")
# Read defaults from .env if they exist
default_provider = os.getenv("DEFAULT_PROVIDER", "Google (Gemini)")
provider_index = 0 if default_provider == "OpenAI" else 1

provider = st.sidebar.radio("LLM Provider", ["OpenAI", "Google (Gemini)"], index=provider_index)

if provider == "OpenAI":
    env_api_key = os.getenv("OPENAI_API_KEY", "")
    env_model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    api_key = st.sidebar.text_input("OpenAI API Key", value=env_api_key, type="password", help="Required: sk-...")
    models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "gpt-4"]
    model_index = models.index(env_model) if env_model in models else 0
    model_choice = st.sidebar.selectbox("LLM Model", models, index=model_index)
    
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
else:
    env_api_key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    env_model = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
    
    api_key = st.sidebar.text_input("Google API Key", value=env_api_key, type="password", help="Required: AIza...")
    model_choice = st.sidebar.text_input("LLM Model", value=env_model, placeholder="gemini-2.5-flash")
    
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        os.environ["GEMINI_API_KEY"] = api_key

app_idea = st.text_input("What are we building today?", placeholder="A Tinder for capybaras...")

# --- STEP 1: DESIGN ---
if st.button("Step 1: Generate Design Spec", type="primary"):
    has_key = (provider == "OpenAI" and os.environ.get("OPENAI_API_KEY")) or \
              (provider == "Google (Gemini)" and os.environ.get("GOOGLE_API_KEY"))
    
    if not has_key:
        st.error(f"Hold up, you need to set your {provider} API key in the sidebar first.")
    elif not app_idea:
        st.warning("Give me an idea first.")
    else:
        with st.spinner(f"Designer is thinking (using {model_choice})..."):
            try:
                st.session_state.designer_output = run_designer(app_idea, model_choice, provider)
                st.session_state.dev_output = None # Reset dev if we do a new design
            except Exception as e:
                st.error(f"API Error: {str(e)}")
                st.write("Double check your API key and make sure you have credits on that model.")

# --- HUMAN IN THE LOOP (Review) ---
if st.session_state.designer_output:
    st.divider()
    st.subheader("📝 Step 1.5 Review Design (Human-in-the-Loop)")
    st.markdown("Here is what the designer came up with. **Edit it directly in this text box** if you hate it or want to add constraints before the developer writes the code.")
    
    edited_spec = st.text_area(
        "Edit the spec if you want:", 
        value=st.session_state.designer_output.raw if hasattr(st.session_state.designer_output, 'raw') else str(st.session_state.designer_output), 
        height=400
    )
    
    # --- STEP 2: BUILD ---
    if st.button("Step 2: Approve & Send to Developer", type="secondary"):
        with st.spinner(f"Developer is writing code (using {model_choice})..."):
            try:
                st.session_state.dev_output = run_developer(edited_spec, model_choice, provider)
            except Exception as e:
                st.error(f"API Error: {str(e)}")

# --- FINAL OUTPUT ---
if st.session_state.dev_output:
    st.divider()
    st.subheader("💻 Final Developer Output")
    st.markdown(st.session_state.dev_output.raw if hasattr(st.session_state.dev_output, 'raw') else str(st.session_state.dev_output))
    st.success("Workflow Complete!")

