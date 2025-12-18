"""Company information extraction service."""

import logging
from typing import Dict, Optional
from pydantic import BaseModel
from pydantic_ai import Agent

from src.providers import get_llm_model

logger = logging.getLogger(__name__)


class CompanyInfo(BaseModel):
    """Structured company information."""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    activities: Optional[str] = None
    context: Optional[str] = None


class CompanyExtractor:
    """Extract structured company information from user input."""

    def __init__(self):
        """Initialize company extractor."""
        self.llm = get_llm_model()
        self.agent = Agent(
            self.llm,
            system_prompt="""You are a company information extraction assistant.
Extract structured company information from user input.
Return a JSON object with fields: company_name, industry, activities, context.
If a field cannot be determined, set it to null."""
        )

    async def extract_company_info(self, user_input: str) -> Dict[str, Optional[str]]:
        """
        Extract company information using LLM.

        Args:
            user_input: User input text that may contain company information

        Returns:
            Dictionary with company_name, industry, activities, context
        """
        try:
            extraction_prompt = f"""Extract company information from the following user input.
Return a JSON object with these fields:
- company_name: The name of the company (if mentioned)
- industry: The industry or sector (if mentioned)
- activities: Business activities or operations (if mentioned)
- context: Any other relevant context about the company

If a field is not mentioned or cannot be determined, set it to null.

User input:
{user_input}

Return only the JSON object, no additional text."""

            result = await self.agent.run(extraction_prompt, response_type=CompanyInfo)
            
            company_info = {
                "company_name": result.data.company_name,
                "industry": result.data.industry,
                "activities": result.data.activities,
                "context": result.data.context
            }
            
            logger.info(f"Extracted company info: {company_info}")
            return company_info

        except Exception as e:
            logger.exception(f"Error extracting company info: {e}")
            # Return empty dict on error
            return {
                "company_name": None,
                "industry": None,
                "activities": None,
                "context": None
            }

