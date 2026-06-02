"""
dynamic_tools_draft.py — Conceptual Draft for Self-Assembly of Tools (LATM)
===========================================================================

This module drafts a production-ready blueprint for how the `agent_dev` platform
can enable agents to write, compile, register, and execute their own custom tools
dynamically at runtime.

How it works:
1. The agent uses the `create_custom_tool` tool to write new Python code.
2. The backend saves this code to a dedicated `backend/dynamic_tools/` folder.
3. The platform dynamically loads all files in that folder during ToolRegistry
   initialization using importlib.
4. The agent can immediately call the new tool in its very next turn.
"""

import os
import sys
import importlib.util
from typing import Any, Dict
from pydantic import BaseModel, Field, create_model

# Folder where custom tools are saved
DYNAMIC_TOOLS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "dynamic_tools")
)
os.makedirs(DYNAMIC_TOOLS_DIR, exist_ok=True)


# =====================================================================
# 1. SCHEMA FOR AGENT TOOL CREATION
# =====================================================================

class CreateCustomToolSchema(BaseModel):
    tool_name: str = Field(
        description="Snake-case unique name for the tool, e.g., 'extract_pdf_metadata'."
    )
    description: str = Field(
        description="Detailed description of what the tool does. The agent will read this in the next tool schema definition."
    )
    parameters: Dict[str, Dict[str, Any]] = Field(
        description=(
            "JSON structure defining the parameters. Example: "
            "{'filepath': {'type': 'string', 'description': 'Path to target PDF'}, "
            " 'extract_images': {'type': 'boolean', 'default': False}}"
        )
    )
    python_code: str = Field(
        description=(
            "Complete Python code containing a `run(**kwargs) -> str` function. "
            "You can import standard libraries or installed workspace packages."
        )
    )


# =====================================================================
# 2. THE DYNAMIC TOOL MAKER CLASS
# =====================================================================

class CreateCustomTool:
    name: str = "create_custom_tool"
    description: str = (
        "Enables you to write and register your own custom Python tools at runtime "
        "when standard tools do not support your specific tasks (e.g. parsing custom formats, calling scrapers)."
    )
    args_schema = CreateCustomToolSchema

    def __init__(self, registry_ref: Any = None):
        self.registry_ref = registry_ref

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, tool_name: str, description: str, parameters: dict, python_code: str) -> str:
        try:
            # Basic validation of Python syntax
            import ast
            ast.parse(python_code)
            
            # Format filename
            filename = f"{tool_name}.py"
            file_path = os.path.join(DYNAMIC_TOOLS_DIR, filename)
            
            # Construct a full standalone class definition module
            # Pydantic's create_model is used to construct the args_schema dynamically!
            module_template = f'''"""
Dynamically generated tool: {tool_name}
"""
import os
from pydantic import BaseModel, Field

# Define parameters schema structure
PARAMS_DEF = {repr(parameters)}

class DynamicArgs(BaseModel):
    pass  # We will augment this model dynamically at load time

def run(**kwargs) -> str:
{chr(10).join("    " + line for line in python_code.splitlines())}
'''
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(module_template)
            
            return (
                f"[SUCCESS] Custom tool '{tool_name}' compiled and saved successfully.\n"
                f"It is registered and will be available in your next execution turn."
            )
            
        except SyntaxError as e:
            return f"[FAILED] Syntax validation failed: Line {e.lineno}: {e.msg}"
        except Exception as e:
            return f"[FAILED] Error creating tool: {str(e)}"


# =====================================================================
# 3. LOADER & REGISTRATION ENGINE
# =====================================================================

class DynamicToolWrapper:
    """Wrapper that turns a dynamically loaded python file into a fully-compliant Registry Tool."""
    def __init__(self, name: str, description: str, args_schema: Any, run_fn: Any):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.run_fn = run_fn

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }

    def run(self, **kwargs) -> str:
        return self.run_fn(**kwargs)


def load_dynamic_tools() -> list:
    """Scans and dynamically imports all custom tools created by the agent."""
    dynamic_tools = []
    
    if not os.path.exists(DYNAMIC_TOOLS_DIR):
        return []
        
    for file in os.listdir(DYNAMIC_TOOLS_DIR):
        if file.endswith(".py") and not file.startswith("__"):
            tool_name = file[:-3]
            file_path = os.path.join(DYNAMIC_TOOLS_DIR, file)
            
            try:
                # Load module dynamically
                spec = importlib.util.spec_from_file_location(tool_name, file_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[tool_name] = module
                spec.loader.exec_module(module)
                
                # Dynamically construct the Pydantic Args Schema
                fields = {}
                for param_name, param_info in module.PARAMS_DEF.items():
                    p_type = str
                    if param_info.get("type") == "boolean":
                        p_type = bool
                    elif param_info.get("type") == "integer":
                        p_type = int
                    elif param_info.get("type") == "number":
                        p_type = float
                    
                    fields[param_name] = (
                        p_type,
                        Field(
                            default=param_info.get("default", ...),
                            description=param_info.get("description", "")
                        )
                    )
                
                dynamic_schema = create_model(f"{tool_name}_schema", **fields)
                
                # Wrap it and register it
                wrapped_tool = DynamicToolWrapper(
                    name=tool_name,
                    description=module.__doc__.strip() if module.__doc__ else f"Custom tool {tool_name}",
                    args_schema=dynamic_schema,
                    run_fn=module.run
                )
                
                dynamic_tools.append(wrapped_tool)
                
            except Exception as e:
                print(f"Error loading dynamic tool {tool_name}: {e}")
                
    return dynamic_tools
