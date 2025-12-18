"""Pydantic models for FastAPI request/response."""

from typing import Optional, List, Dict, Any
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


class QAPair(BaseModel):
    """Q&A pair model."""
    _id: Optional[str] = None
    session_id: Optional[str] = None
    question: str
    original_answer: Optional[str] = None
    edited_answer: Optional[str] = None
    final_answer: str = ""
    citations: List[Citation] = Field(default_factory=list)
    qa_pair_id: Optional[str] = None
    question_index: int
    outcome_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @model_validator(mode='before')
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        """Normalize field names from different sources."""
        if isinstance(data, dict):
            # Map 'answer' to 'final_answer' if 'answer' is provided but 'final_answer' is not
            if 'answer' in data and 'final_answer' not in data:
                data['final_answer'] = data['answer']
            # Map 'qa_pair_id' to '_id' if provided
            if 'qa_pair_id' in data and '_id' not in data:
                data['_id'] = data['qa_pair_id']
            # Ensure final_answer has a value (use answer if available, otherwise empty string)
            if 'final_answer' not in data:
                data['final_answer'] = data.get('answer', '')
        return data
    
    def model_dump(self, **kwargs):
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

