import os
from typing import Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class UpdateSpecSchema(BaseModel):
    updated_spec: str = Field(
        description="The complete, updated specification document in Markdown format."
    )
    change_summary: str = Field(
        description="A brief summary of what was changed and why, in 2-4 bullet points. Example: '- Added authentication section with JWT tokens\n- Changed database from SQLite to PostgreSQL\n- Added responsive mobile layout requirements'"
    )


class UpdateSpecTool(BaseTool):
    name: str = "Update Specification"
    description: str = (
        "Saves the updated specification and records what changed. You MUST call this tool to save your spec — do NOT just output raw markdown. Always include a clear change_summary explaining what was added, modified, or removed."
    )
    args_schema: type[BaseModel] = UpdateSpecSchema
    result_holder: dict = {}

    def __init__(self, result_holder: dict, **kwargs):
        super().__init__(**kwargs)
        self.result_holder = result_holder

    def _run(self, updated_spec: str, change_summary: str) -> str:
        """Save the spec and change summary."""
        self.result_holder["spec"] = updated_spec
        self.result_holder["summary"] = change_summary
        return f"[SUCCESS] Specification saved. Changes: {change_summary}"
