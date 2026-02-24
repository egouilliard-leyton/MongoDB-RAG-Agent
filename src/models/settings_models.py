"""Pydantic models for application settings and version history."""

from typing import Optional, List, Union
from pydantic import BaseModel, Field, model_validator, ConfigDict
from datetime import datetime


class SearchParamsOverride(BaseModel):
    """Optional overrides for search parameters at stage or default level."""

    match_count: Optional[int] = Field(default=None, ge=1, le=50)
    rrf_k: Optional[int] = Field(default=None, ge=1, le=200)
    qa_history_match_count: Optional[int] = Field(default=None, ge=0, le=20)


class StageDefaultConfig(BaseModel):
    """Default stage configuration applied to all stages unless overridden."""

    system_prompt_append: Optional[str] = None
    search_params: SearchParamsOverride = Field(default_factory=SearchParamsOverride)


class GlobalSettings(BaseModel):
    """All 16 configurable application settings. API keys are excluded."""

    main_system_prompt: str = Field(..., min_length=1)
    follow_up_context_prompt: str = Field(..., min_length=1)
    qa_history_prompt: str = Field(..., min_length=1)
    stage_defaults: StageDefaultConfig = Field(default_factory=StageDefaultConfig)
    default_match_count: int = Field(default=10, ge=1, le=50)
    max_match_count: int = Field(default=50, ge=1, le=200)
    enable_question_decomposition: bool = True
    enable_iterative_refinement: bool = True
    enable_qa_history_search: bool = True
    rrf_k_constant: int = Field(default=60, ge=1, le=200)
    qa_history_match_count: int = Field(default=3, ge=0, le=20)
    llm_model: str = Field(default="anthropic/claude-haiku-4.5")
    llm_base_url: str = Field(default="https://openrouter.ai/api/v1")
    embedding_model: str = Field(default="text-embedding-3-small")
    show_full_citations: bool = False


class SettingsUpdateRequest(BaseModel):
    """Partial update request. At least one field must be provided."""

    main_system_prompt: Optional[str] = Field(default=None, min_length=1)
    follow_up_context_prompt: Optional[str] = Field(default=None, min_length=1)
    qa_history_prompt: Optional[str] = Field(default=None, min_length=1)
    stage_defaults: Optional[StageDefaultConfig] = None
    default_match_count: Optional[int] = Field(default=None, ge=1, le=50)
    max_match_count: Optional[int] = Field(default=None, ge=1, le=200)
    enable_question_decomposition: Optional[bool] = None
    enable_iterative_refinement: Optional[bool] = None
    enable_qa_history_search: Optional[bool] = None
    rrf_k_constant: Optional[int] = Field(default=None, ge=1, le=200)
    qa_history_match_count: Optional[int] = Field(default=None, ge=0, le=20)
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    embedding_model: Optional[str] = None
    show_full_citations: Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "SettingsUpdateRequest":
        """Ensure at least one field is provided."""
        has_value = any(
            getattr(self, f) is not None
            for f in self.model_fields
        )
        if not has_value:
            raise ValueError("At least one settings field must be provided")
        return self


class SettingsResponse(BaseModel):
    """Response model for current settings."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    version: int
    main_system_prompt: str
    follow_up_context_prompt: str
    qa_history_prompt: str
    stage_defaults: StageDefaultConfig
    default_match_count: int
    max_match_count: int
    enable_question_decomposition: bool
    enable_iterative_refinement: bool
    enable_qa_history_search: bool
    rrf_k_constant: int
    qa_history_match_count: int
    llm_model: str
    llm_base_url: str
    embedding_model: str
    show_full_citations: bool
    updated_at: datetime


class SettingsVersion(BaseModel):
    """A historical settings version entry."""

    version: int
    changed_fields: List[str] = Field(default_factory=list)
    summary: str
    created_at: datetime


class ParameterSuggestion(BaseModel):
    """AI-generated parameter tuning suggestion."""

    suggestion_id: str
    parameter: str
    current_value: Union[int, str, bool, float]
    suggested_value: Union[int, str, bool, float]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class PromptTestRequest(BaseModel):
    """Request body for prompt testing endpoint."""

    prompt: str = Field(..., min_length=1)
    test_question: str = Field(..., min_length=1)


class PromptTestResponse(BaseModel):
    """Response for prompt testing endpoint."""

    answer: str
    latency_ms: int
