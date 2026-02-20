"""Pydantic models for FastAPI request/response."""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator, field_validator, ConfigDict
from datetime import datetime


class CompanyInfo(BaseModel):
    """Company information model."""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    activities: Optional[str] = None
    context: Optional[str] = None


class SessionCreateRequest(BaseModel):
    """Request model for creating a session."""
    name: str = Field(..., min_length=1, max_length=500, description="Session name")
    user_role: str = Field(..., description="User role: 'junior' or 'senior'")
    company_info: Optional[str] = Field(None, max_length=5000, description="Optional company information as string (will be parsed)")
    project_id: Optional[str] = Field(
        None, description="Optional project ID to scope the session (ObjectId as string)"
    )
    tax_office_id: Optional[int] = Field(
        default=None, description="Tax office ID (kodjednostki)"
    )
    region: Optional[str] = Field(
        default=None, max_length=50, description="Region (voivodeship)"
    )
    
    @field_validator('user_role')
    @classmethod
    def validate_user_role(cls, v: str) -> str:
        """Validate user_role is 'junior' or 'senior'."""
        v_lower = v.lower().strip()
        if v_lower not in ("junior", "senior"):
            raise ValueError("user_role must be 'junior' or 'senior'")
        return v_lower
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate session name is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Session name cannot be empty")
        return v


class SessionResponse(BaseModel):
    """Response model for session."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id", serialization_alias="_id")
    session_name: str
    user_role: str
    status: str
    outcome_status: Optional[str]
    project_id: Optional[str] = None
    tax_office_id: Optional[int] = Field(default=None, description="Tax office ID (kodjednostki)")
    region: Optional[str] = Field(default=None, description="Region (voivodeship)")
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class QuestionProcessRequest(BaseModel):
    """Request model for processing questions."""
    questions: List[str] = Field(..., min_length=1, max_length=100, description="List of questions to process")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    user_role: str = Field(default="junior", description="User role")
    include_history: bool = Field(default=True, description="Include Q&A history in search")
    
    @field_validator('user_role')
    @classmethod
    def validate_user_role(cls, v: str) -> str:
        """Validate user_role is 'junior' or 'senior'."""
        v_lower = v.lower().strip()
        if v_lower not in ("junior", "senior"):
            raise ValueError("user_role must be 'junior' or 'senior'")
        return v_lower
    
    @field_validator('questions')
    @classmethod
    def validate_questions(cls, v: List[str]) -> List[str]:
        """Validate questions list."""
        if not v:
            raise ValueError("Questions list cannot be empty")
        if len(v) > 100:
            raise ValueError(f"Too many questions: {len(v)}. Maximum allowed: 100")
        
        validated = []
        for i, question in enumerate(v):
            if not isinstance(question, str):
                raise ValueError(f"Question at index {i} must be a string")
            question = question.strip()
            if not question:
                raise ValueError(f"Question at index {i} cannot be empty")
            if len(question) > 10000:
                raise ValueError(f"Question at index {i} is too long (max 10000 characters)")
            validated.append(question)
        
        return validated


class Citation(BaseModel):
    """Citation model."""
    citation_number: int
    title: str
    source: str
    document_id: str
    document_title: Optional[str] = None  # Frontend expects this
    similarity: Optional[float] = None
    chunk_id: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def normalize_title(cls, data: Any) -> Any:
        """Ensure document_title is set from title if not provided."""
        if isinstance(data, dict):
            if 'document_title' not in data and 'title' in data:
                data['document_title'] = data['title']
            elif 'title' not in data and 'document_title' in data:
                data['title'] = data['document_title']
        return data


ALLOWED_QA_OUTCOME_STATUSES = ("successful", "partial", "negative")


class QAPair(BaseModel):
    """Q&A pair model."""
    model_config = ConfigDict(populate_by_name=True)

    # NOTE: Pydantic treats underscore-prefixed attributes specially; use an internal
    # `id` field and alias it to `_id` so JSON payloads include `_id` consistently.
    id: Optional[str] = Field(default=None, alias="_id", serialization_alias="_id")
    session_id: Optional[str] = None
    question: str
    original_answer: Optional[str] = None
    edited_answer: Optional[str] = None
    final_answer: str = ""
    # Consultant feedback / review fields
    rating_good: Optional[bool] = None  # null = not reviewed
    rated_at: Optional[datetime] = None
    rated_by: Optional[str] = None
    # Editing audit fields
    was_edited: bool = False
    edited_at: Optional[datetime] = None
    review: Optional[Dict[str, Any]] = None
    citations: List[Citation] = Field(default_factory=list)
    qa_pair_id: Optional[str] = None
    question_index: int
    outcome_status: Optional[str] = Field(
        default=None,
        description="Outcome status: 'successful', 'partial', or 'negative'"
    )
    is_exemplar: bool = Field(
        default=False,
        description="Whether this Q&A pair is an exemplar (high-quality reference)"
    )
    promoted_to_exemplar_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when this Q&A pair was promoted to exemplar status"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('outcome_status')
    @classmethod
    def validate_outcome_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate outcome_status is one of the allowed values."""
        if v is None:
            return v
        v_lower = v.lower().strip()
        if v_lower not in ALLOWED_QA_OUTCOME_STATUSES:
            raise ValueError(
                f"outcome_status must be one of: {', '.join(ALLOWED_QA_OUTCOME_STATUSES)}"
            )
        return v_lower
    
    @model_validator(mode='before')
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        """Normalize field names from different sources."""
        if isinstance(data, dict):
            # Map 'answer' to 'final_answer' if 'answer' is provided but 'final_answer' is not
            if 'answer' in data and 'final_answer' not in data:
                data['final_answer'] = data['answer']
            # Ensure we always expose a MongoDB id as `_id` in JSON.
            # Some code paths return `qa_pair_id` instead of `_id`.
            if not data.get('_id') and data.get('qa_pair_id'):
                data['_id'] = data['qa_pair_id']
            # Keep `qa_pair_id` redundant/backward-compatible if only `_id` exists.
            if not data.get('qa_pair_id') and data.get('_id'):
                data['qa_pair_id'] = data['_id']
            # Ensure final_answer has a value (use answer if available, otherwise empty string)
            if 'final_answer' not in data:
                data['final_answer'] = data.get('answer', '')
        return data

    @field_validator("id", "session_id", mode="before")
    @classmethod
    def coerce_object_ids_to_str(cls, v: Any) -> Any:
        """Coerce BSON ObjectIds (or similar) to strings."""
        if v is None:
            return v
        # bson is already a dependency (used in routes); guard import anyway.
        try:
            from bson import ObjectId
            if isinstance(v, ObjectId):
                return str(v)
        except Exception:
            pass
        return str(v) if not isinstance(v, str) else v
    
    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        """Ensure final_answer is always present in output."""
        data = super().model_dump(**kwargs)
        if not data.get('final_answer') and data.get('answer'):
            data['final_answer'] = data['answer']
        return data


class QuestionProcessResponse(BaseModel):
    """Response model for question processing."""
    questions_processed: int
    qa_pairs: List[QAPair]


class QAPairUpdateRequest(BaseModel):
    """Request model for updating a Q&A pair."""
    edited_answer: str = Field(..., min_length=1, max_length=50000, description="Edited answer text")
    
    @field_validator('edited_answer')
    @classmethod
    def validate_edited_answer(cls, v: str) -> str:
        """Validate edited answer is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Edited answer cannot be empty")
        return v


class QAPairRatingUpdateRequest(BaseModel):
    """Request model for updating a Q&A pair rating."""
    rating_good: Optional[bool] = Field(
        ...,
        description="Consultant rating: true=good, false=bad, null=not reviewed"
    )


class QAPairOutcomeUpdateRequest(BaseModel):
    """Request model for updating a Q&A pair outcome status."""
    outcome_status: str = Field(
        ...,
        description="Outcome status: 'successful', 'partial', or 'negative'"
    )

    @field_validator('outcome_status')
    @classmethod
    def validate_outcome_status(cls, v: str) -> str:
        """Validate outcome_status is one of the allowed values."""
        v_lower = v.lower().strip()
        if v_lower not in ALLOWED_QA_OUTCOME_STATUSES:
            raise ValueError(
                f"outcome_status must be one of: {', '.join(ALLOWED_QA_OUTCOME_STATUSES)}"
            )
        return v_lower


class FollowUpSessionRequest(BaseModel):
    """Request model for creating follow-up session."""
    new_questions: List[str] = Field(..., min_length=1, max_length=100, description="New questions for follow-up session")
    
    @field_validator('new_questions')
    @classmethod
    def validate_new_questions(cls, v: List[str]) -> List[str]:
        """Validate new questions list."""
        if not v:
            raise ValueError("New questions list cannot be empty")
        if len(v) > 100:
            raise ValueError(f"Too many questions: {len(v)}. Maximum allowed: 100")
        
        validated = []
        for i, question in enumerate(v):
            if not isinstance(question, str):
                raise ValueError(f"Question at index {i} must be a string")
            question = question.strip()
            if not question:
                raise ValueError(f"Question at index {i} cannot be empty")
            if len(question) > 10000:
                raise ValueError(f"Question at index {i} is too long (max 10000 characters)")
            validated.append(question)
        
        return validated


class OutcomeUpdateRequest(BaseModel):
    """Request model for updating session outcome."""
    outcome: str = Field(..., description="Outcome: 'successful' or 'unsuccessful'")
    determined_by: str = Field(default="user", description="Who determined outcome: 'user' or 'auto'")
    
    @field_validator('outcome')
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        """Validate outcome is 'successful' or 'unsuccessful'."""
        v_lower = v.lower().strip()
        if v_lower not in ("successful", "unsuccessful"):
            raise ValueError("outcome must be 'successful' or 'unsuccessful'")
        return v_lower
    
    @field_validator('determined_by')
    @classmethod
    def validate_determined_by(cls, v: str) -> str:
        """Validate determined_by is 'user' or 'auto'."""
        v_lower = v.lower().strip()
        if v_lower not in ("user", "auto"):
            raise ValueError("determined_by must be 'user' or 'auto'")
        return v_lower


class ProjectCreateRequest(BaseModel):
    """Request model for creating a project."""
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    company_info: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional company info payload"
    )
    tax_office_id: Optional[int] = Field(
        default=None, description="Tax office ID (kodjednostki)"
    )
    region: Optional[str] = Field(
        default=None, max_length=50, description="Region (voivodeship)"
    )
    industry: Optional[str] = Field(
        default=None, max_length=100, description="Industry classification"
    )


class ProjectStage(BaseModel):
    key: str
    updated_at: datetime


class ProjectResponse(BaseModel):
    """Response model for project."""
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias="_id", serialization_alias="_id")
    name: str
    company_info: Dict[str, Any] = Field(default_factory=dict)
    tax_office_id: Optional[int] = Field(default=None, description="Tax office ID (kodjednostki)")
    region: Optional[str] = Field(default=None, description="Region (voivodeship)")
    industry: Optional[str] = Field(default=None, description="Industry classification")
    created_at: datetime
    updated_at: datetime
    stage: ProjectStage
    stage_history: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectStageUpdateRequest(BaseModel):
    """
    Request model to transition project stage.

    If `mode="transition"` the (event,to_stage) must be a valid transition from current stage.
    If `mode="rollback"` we allow setting a previous stage (must still be a known key).
    """
    mode: Literal["transition", "rollback", "force"] = Field(
        default="transition", description="How to apply stage update"
    )
    event: str = Field(..., min_length=1, max_length=50, description="Transition event")
    to_stage: str = Field(..., min_length=1, max_length=80, description="Target stage key")
    note: Optional[str] = Field(default=None, max_length=500, description="Optional note")


# Reference Data Models

class TaxOffice(BaseModel):
    """
    Tax Office (Urząd Skarbowy) model.

    Represents one of 590 Polish tax offices with complete contact information.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id", serialization_alias="_id")
    kodjednostki: int = Field(..., description="Unique tax office ID")
    nazwa_urzedu: str = Field(..., description="Office name")
    typ: str = Field(..., description="Type (IAS/US)")
    wojewodztwo: str = Field(..., description="Region (voivodeship)")
    miasto: str = Field(..., description="City")
    ulica: str = Field(..., description="Street")
    nr_budynku: str = Field(..., description="Building number")
    kod_pocztowy: str = Field(..., description="Postal code")
    telefon: str = Field(..., description="Phone number")
    email: str = Field(..., description="Email address")
    adres_bip: str = Field(..., description="BIP website URL")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_object_id_to_str(cls, v: Any) -> Any:
        """Coerce BSON ObjectId to string."""
        if v is None:
            return v
        try:
            from bson import ObjectId
            if isinstance(v, ObjectId):
                return str(v)
        except Exception:
            pass
        return str(v) if not isinstance(v, str) else v


class Region(BaseModel):
    """
    Region (Voivodeship) model.

    Represents one of 16 Polish voivodeships.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id", serialization_alias="_id")
    name: str = Field(..., description="Region name (Polish)")
    display_name: str = Field(..., description="Display name for UI")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_object_id_to_str(cls, v: Any) -> Any:
        """Coerce BSON ObjectId to string."""
        if v is None:
            return v
        try:
            from bson import ObjectId
            if isinstance(v, ObjectId):
                return str(v)
        except Exception:
            pass
        return str(v) if not isinstance(v, str) else v


class Industry(BaseModel):
    """
    Industry classification model.

    Represents one of 19 predefined industry categories.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id", serialization_alias="_id")
    name_polish: str = Field(..., description="Industry name in Polish")
    name_english: str = Field(..., description="Industry name in English")
    code: str = Field(..., description="Short code identifier")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_object_id_to_str(cls, v: Any) -> Any:
        """Coerce BSON ObjectId to string."""
        if v is None:
            return v
        try:
            from bson import ObjectId
            if isinstance(v, ObjectId):
                return str(v)
        except Exception:
            pass
        return str(v) if not isinstance(v, str) else v

