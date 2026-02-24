"""Settings configuration for MongoDB RAG Agent."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from dotenv import load_dotenv
from typing import Any, Dict, Optional
import logging

# Try to load environment variables from .env file, but don't fail if inaccessible
try:
    load_dotenv()
except (PermissionError, OSError):
    # .env file may be locked or inaccessible, continue with environment variables only
    pass


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore", env_ignore_empty=True
    )

    # MongoDB Configuration
    mongodb_uri: str = Field(..., description="MongoDB Atlas connection string")

    mongodb_database: str = Field(default="rag_db", description="MongoDB database name")

    mongodb_collection_documents: str = Field(
        default="documents", description="Collection for source documents"
    )

    mongodb_collection_chunks: str = Field(
        default="chunks", description="Collection for document chunks with embeddings"
    )

    mongodb_collection_qa_sessions: str = Field(
        default="qa_sessions", description="Collection for Q&A sessions"
    )

    mongodb_collection_qa_pairs: str = Field(
        default="qa_pairs", description="Collection for Q&A pairs"
    )

    mongodb_collection_tax_offices: str = Field(
        default="tax_offices", description="Collection for tax office reference data"
    )

    mongodb_collection_regions: str = Field(
        default="regions", description="Collection for region reference data"
    )

    mongodb_collection_industries: str = Field(
        default="industries", description="Collection for industry reference data"
    )

    mongodb_collection_projects: str = Field(
        default="projects", description="Collection for projects"
    )

    mongodb_collection_app_settings: str = Field(
        default="app_settings", description="Collection for application settings and version history"
    )

    mongodb_collection_workflow_templates: str = Field(
        default="workflow_templates", description="Collection for workflow templates"
    )

    qa_auto_success_days: int = Field(
        default=30, description="Days after export to auto-mark session as successful"
    )

    qa_background_check_enabled: bool = Field(
        default=True, description="Enable background task scheduler for auto-success detection"
    )

    qa_background_check_interval_hours: int = Field(
        default=24, description="Interval in hours between background checks (default: 24 hours)"
    )

    mongodb_vector_index: str = Field(
        default="vector_index",
        description="Vector search index name (must be created in Atlas UI)",
    )

    mongodb_text_index: str = Field(
        default="text_index",
        description="Full-text search index name (must be created in Atlas UI)",
    )

    # LLM Configuration (OpenAI-compatible)
    llm_provider: str = Field(
        default="openrouter",
        description="LLM provider (openai, anthropic, gemini, ollama, etc.)",
    )

    llm_api_key: str = Field(..., description="API key for the LLM provider")

    llm_model: str = Field(
        default="anthropic/claude-haiku-4.5",
        description="Model to use for search and summarization",
    )

    llm_base_url: Optional[str] = Field(
        default="https://openrouter.ai/api/v1",
        description="Base URL for the LLM API (for OpenAI-compatible providers)",
    )

    # Embedding Configuration
    embedding_provider: str = Field(default="openai", description="Embedding provider")

    embedding_api_key: str = Field(..., description="API key for embedding provider")

    embedding_model: str = Field(
        default="text-embedding-3-small", description="Embedding model to use"
    )

    embedding_base_url: Optional[str] = Field(
        default="https://api.openai.com/v1", description="Base URL for embedding API"
    )

    embedding_dimension: int = Field(
        default=1536,
        description="Embedding vector dimension (1536 for text-embedding-3-small)",
    )

    # Gemini API Configuration (for industry classification)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for industry classification",
    )

    # Search Configuration
    default_match_count: int = Field(
        default=10, description="Default number of search results to return"
    )

    max_match_count: int = Field(
        default=50, description="Maximum number of search results allowed"
    )

    default_text_weight: float = Field(
        default=0.3, description="Default text weight for hybrid search (0-1)"
    )

    # Citation Configuration
    show_full_citations: bool = Field(
        default=False, description="Show full citations with source and path (True) or just title with link (False)"
    )
    
    # Agentic RAG Configuration
    enable_question_decomposition: bool = Field(
        default=True, description="Enable automatic question decomposition into sub-questions"
    )
    
    enable_iterative_refinement: bool = Field(
        default=True, description="Enable iterative search refinement based on results"
    )
    
    max_decomposition_depth: int = Field(
        default=3, description="Maximum depth for question decomposition (prevent infinite loops)"
    )
    
    max_search_iterations: int = Field(
        default=3, description="Maximum number of search iterations for refinement"
    )
    
    @field_validator('show_full_citations', mode='before')
    @classmethod
    def parse_show_full_citations(cls, v: Any) -> bool:
        """Parse show_full_citations from various string formats."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ('true', '1', 'yes', 'on'):
                return True
            if v_lower in ('false', '0', 'no', 'off', ''):
                return False
        return bool(v) if v is not None else False


def load_settings() -> Settings:
    """Load settings with proper error handling."""
    try:
        return Settings()  # type: ignore[call-arg]  # Pydantic Settings loads from environment
    except PermissionError as e:
        # .env file is locked/inaccessible, try loading from environment only
        if ".env" in str(e):
            # Create settings without trying to read .env file
            original_config = Settings.model_config
            Settings.model_config = SettingsConfigDict(
                case_sensitive=False, extra="ignore", env_ignore_empty=True
            )
            try:
                settings = Settings()  # type: ignore[call-arg]
                Settings.model_config = original_config
                return settings
            except Exception as inner_e:
                Settings.model_config = original_config
                error_msg = f"Failed to load settings from environment: {inner_e}"
                if "mongodb_uri" in str(inner_e).lower():
                    error_msg += "\nMake sure to set MONGODB_URI environment variable"
                if "llm_api_key" in str(inner_e).lower():
                    error_msg += "\nMake sure to set LLM_API_KEY environment variable"
                if "embedding_api_key" in str(inner_e).lower():
                    error_msg += "\nMake sure to set EMBEDDING_API_KEY environment variable"
                raise ValueError(error_msg) from inner_e
        raise
    except Exception as e:
        error_msg = f"Failed to load settings: {e}"
        if "mongodb_uri" in str(e).lower():
            error_msg += "\nMake sure to set MONGODB_URI in your .env file or environment"
        if "llm_api_key" in str(e).lower():
            error_msg += "\nMake sure to set LLM_API_KEY in your .env file or environment"
        if "embedding_api_key" in str(e).lower():
            error_msg += "\nMake sure to set EMBEDDING_API_KEY in your .env file or environment"
        raise ValueError(error_msg) from e


_logger = logging.getLogger(__name__)


async def load_runtime_settings(db: Any) -> Dict[str, Any]:
    """
    Load runtime settings from MongoDB, merged over env-based defaults.

    Falls back to env-only settings if MongoDB is unavailable.

    Args:
        db: Motor database instance.

    Returns:
        Dictionary of resolved settings values.
    """
    env_settings = load_settings()

    # Build base dict from env
    base: Dict[str, Any] = {
        "default_match_count": env_settings.default_match_count,
        "max_match_count": env_settings.max_match_count,
        "enable_question_decomposition": env_settings.enable_question_decomposition,
        "enable_iterative_refinement": env_settings.enable_iterative_refinement,
        "enable_qa_history_search": True,
        "rrf_k_constant": 60,
        "qa_history_match_count": 3,
        "llm_model": env_settings.llm_model,
        "llm_base_url": env_settings.llm_base_url or "https://openrouter.ai/api/v1",
        "embedding_model": env_settings.embedding_model,
        "show_full_citations": env_settings.show_full_citations,
    }

    try:
        from src.services.settings_service import SettingsService

        svc = SettingsService(env_settings)
        svc.db = db
        # Reuse the existing db connection — skip initialize/cleanup
        svc.mongo_client = True  # type: ignore[assignment]  # mark as "connected"

        doc = await svc.get_current()

        # Merge MongoDB values over base
        for key in base:
            if key in doc and doc[key] is not None:
                base[key] = doc[key]

        # Include prompt-related fields
        for key in ("main_system_prompt", "follow_up_context_prompt", "qa_history_prompt", "stage_defaults"):
            if key in doc:
                base[key] = doc[key]

    except Exception as e:
        _logger.warning(f"Failed to load runtime settings from MongoDB: {e}. Using env defaults.")

    return base
