"""Pydantic models for workflow templates and stages."""

from typing import Optional, Literal, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from src.models.settings_models import SearchParamsOverride

WorkflowType = Literal["project", "qa_session", "qa_pair", "agentic"]


class TransitionCondition(BaseModel):
    """Condition that must be met for a stage transition."""

    type: str
    params: Optional[dict[str, Any]] = None


class MetadataFieldDef(BaseModel):
    """Definition of a metadata field collected at a stage."""

    key: str
    label: str
    field_type: Literal["text", "number", "date", "select"]
    required: bool = False
    options: Optional[list[str]] = None  # only for "select" type


class StageConfig(BaseModel):
    """Configuration for a workflow stage."""

    system_prompt_append: Optional[str] = None
    search_params: SearchParamsOverride = Field(default_factory=SearchParamsOverride)
    metadata_fields: list[MetadataFieldDef] = Field(default_factory=list)
    auto_advance: bool = False


class StageTransition(BaseModel):
    """A possible transition from one stage to another."""

    to_stage_id: str
    label: str
    condition: Optional[TransitionCondition] = None


class WorkflowStage(BaseModel):
    """A single stage within a workflow template."""

    id: str
    label: str
    description: str = ""
    order: int
    color: str = "#3B82F6"
    config: StageConfig = Field(default_factory=StageConfig)
    transitions: list[StageTransition] = Field(default_factory=list)


class WorkflowCreateRequest(BaseModel):
    """Request body for creating or updating a workflow template."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    is_default: bool = False
    workflow_type: WorkflowType = "project"
    stages: list[WorkflowStage] = Field(default_factory=list)


class WorkflowDuplicateRequest(BaseModel):
    """Request body for duplicating a workflow template."""

    name: Optional[str] = None  # If None, use "Copy of <original name>"


class WorkflowResponse(BaseModel):
    """Full workflow template response."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str
    is_default: bool
    workflow_type: WorkflowType = "project"
    stages: list[WorkflowStage]
    created_at: datetime
    updated_at: datetime


class WorkflowListItem(BaseModel):
    """Summary item for workflow template listing."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str
    is_default: bool
    workflow_type: WorkflowType = "project"
    stage_count: int
    created_at: datetime
    updated_at: datetime
