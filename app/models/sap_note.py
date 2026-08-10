"""Domain models: SAP Note metadata, validation and analysis results."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SAPNoteInput(BaseModel):
    """A single SAP Note supplied by the user (input side)."""

    note_number: str = Field(..., description="SAP Note number, e.g. '3021123'")
    title: str | None = None
    description: str | None = None
    source: str = Field(
        "manual",
        description="How the note was provided: manual | upload | link | prompt",
    )
    attachments: list[str] = Field(default_factory=list)


class SAPNoteMetadata(BaseModel):
    """Metadata resolved for an SAP Note (post lookup / mock lookup)."""

    note_number: str
    title: str = ""
    version: str = ""
    release_status: str = "released"  # released | obsolete
    component: str = ""
    valid_releases: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    kind: str = "correction"  # correction | prerequisite | consulting
    manual_activities: bool = False
    long_text: str = ""


class NoteValidationResult(BaseModel):
    """Aggregate validation outcome for a note against a target system."""

    note_number: str
    valid: bool = True
    checks: dict[str, bool] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    prerequisites_ordered: list[str] = Field(default_factory=list)
    already_implemented: bool = False
    obsolete: bool = False
    can_implement: bool = True


class NoteAnalysisResult(BaseModel):
    """AI-produced analysis of a note (or a set of notes)."""

    executive_summary: str = ""
    business_impact: str = ""
    technical_impact: str = ""
    implementation_sequence: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    predicted_conflicts: list[str] = Field(default_factory=list)
    recommended_prereqs: list[str] = Field(default_factory=list)
    raw_llm_text: str = ""
    llm_provider: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)