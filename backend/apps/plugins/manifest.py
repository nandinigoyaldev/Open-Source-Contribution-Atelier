import re
from typing import List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class PluginManifest(BaseModel):
    name: str
    display_name: str
    version: str
    api_version: str
    description: str
    author: str
    entry_point: str = ""
    dependencies: List[str] = Field(default_factory=list)
    hooks: Dict[str, str] = Field(default_factory=dict)  # e.g. "on_install": "hooks.on_install"
    views: Dict[str, str] = Field(default_factory=dict)  # e.g. "info/": "views.GitHubStatsInfoView"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Plugin name must contain only alphanumeric characters, underscores, and dashes.")
        return v

def validate_manifest(data: dict) -> PluginManifest:
    """Validates raw dictionary manifest against the schema."""
    return PluginManifest(**data)
