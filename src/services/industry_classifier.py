"""Industry classification service using Google Gemini API.

This service provides automatic industry classification for documents
using Google's Gemini API File Search capabilities.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import google.generativeai as genai

from src.settings import load_settings

logger = logging.getLogger(__name__)

# 19 predefined industries from client list (Polish with English translations)
INDUSTRIES = [
    {"code": "MACHINERY", "name_polish": "Branża produkcji maszyn", "name_english": "Machinery production"},
    {"code": "IT", "name_polish": "Branża IT", "name_english": "IT"},
    {"code": "METALLURGY", "name_polish": "Branża metalurgiczna", "name_english": "Metallurgical"},
    {"code": "CONSTRUCTION", "name_polish": "Branża budowlana", "name_english": "Construction"},
    {"code": "FOOD", "name_polish": "Branża spożywcza", "name_english": "Food"},
    {"code": "PACKAGING", "name_polish": "Branża opakowań i tworzyw sztucznych", "name_english": "Packaging & plastics"},
    {"code": "FURNITURE", "name_polish": "Branża meblowa", "name_english": "Furniture"},
    {"code": "STEEL", "name_polish": "Branża konstrukcji stalowych", "name_english": "Steel construction"},
    {"code": "TEXTILE", "name_polish": "Branża tekstylna", "name_english": "Textile"},
    {"code": "PHARMA", "name_polish": "Branża kosmetyczna, farmaceutyczna, medyczna", "name_english": "Cosmetic, pharmaceutical, medical"},
    {"code": "CHEMICAL", "name_polish": "Branża chemiczna", "name_english": "Chemical"},
    {"code": "PRINTING", "name_polish": "Branża poligraficzna", "name_english": "Printing"},
    {"code": "AUTOMOTIVE", "name_polish": "Branża automotive", "name_english": "Automotive"},
    {"code": "ENERGY", "name_polish": "Branża energetyczna", "name_english": "Energy"},
    {"code": "HVAC", "name_polish": "Branża HVAC", "name_english": "HVAC"},
    {"code": "ARCHITECTURE", "name_polish": "Branża architektoniczna", "name_english": "Architectural"},
    {"code": "BIOTECH", "name_polish": "Branża biotechnologiczna", "name_english": "Biotechnology"},
    {"code": "RECYCLING", "name_polish": "Branża recyklingowa", "name_english": "Recycling"},
    {"code": "SHIPYARD", "name_polish": "Branża stoczniowa", "name_english": "Shipyard"},
]

# Classification prompt template
CLASSIFICATION_PROMPT = """Analyze the provided document and classify the company/organization into ONE of the following 19 industry categories.

INDUSTRY OPTIONS:
1. Branża produkcji maszyn (Machinery production) - Code: MACHINERY
2. Branża IT (IT) - Code: IT
3. Branża metalurgiczna (Metallurgical) - Code: METALLURGY
4. Branża budowlana (Construction) - Code: CONSTRUCTION
5. Branża spożywcza (Food) - Code: FOOD
6. Branża opakowań i tworzyw sztucznych (Packaging & plastics) - Code: PACKAGING
7. Branża meblowa (Furniture) - Code: FURNITURE
8. Branża konstrukcji stalowych (Steel construction) - Code: STEEL
9. Branża tekstylna (Textile) - Code: TEXTILE
10. Branża kosmetyczna, farmaceutyczna, medyczna (Cosmetic, pharmaceutical, medical) - Code: PHARMA
11. Branża chemiczna (Chemical) - Code: CHEMICAL
12. Branża poligraficzna (Printing) - Code: PRINTING
13. Branża automotive (Automotive) - Code: AUTOMOTIVE
14. Branża energetyczna (Energy) - Code: ENERGY
15. Branża HVAC (HVAC) - Code: HVAC
16. Branża architektoniczna (Architectural) - Code: ARCHITECTURE
17. Branża biotechnologiczna (Biotechnology) - Code: BIOTECH
18. Branża recyklingowa (Recycling) - Code: RECYCLING
19. Branża stoczniowa (Shipyard) - Code: SHIPYARD

Based on the document content, determine the PRIMARY industry that best describes the company or organization.

Look for indicators such as:
- Company name and description
- Products or services mentioned
- Technical terminology specific to an industry
- Business activities described
- Partners, clients, or suppliers mentioned

IMPORTANT:
- Choose the SINGLE most appropriate industry
- If the document doesn't clearly indicate an industry, respond with "UNKNOWN"
- Respond with ONLY the industry code in uppercase (e.g., "IT", "AUTOMOTIVE", "PHARMA")

Your response should be a single word - the industry code."""


class IndustryClassifier:
    """
    Service for classifying documents into industry categories using Gemini API.

    This classifier uploads documents to Gemini, uses the File Search API
    to analyze content, and returns the most appropriate industry classification.
    """

    def __init__(self):
        """Initialize the IndustryClassifier with Gemini API configuration."""
        self.settings = load_settings()
        self._configured = False
        self._configure_api()

    def _configure_api(self) -> None:
        """Configure the Gemini API with the API key from settings."""
        if not self.settings.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY not configured. Industry classification will be unavailable."
            )
            return

        try:
            genai.configure(api_key=self.settings.gemini_api_key)
            self._configured = True
            logger.info("Gemini API configured successfully")
        except Exception as e:
            logger.exception(f"Failed to configure Gemini API: {e}")
            self._configured = False

    @property
    def is_available(self) -> bool:
        """Check if the classifier is available (API key configured)."""
        return self._configured

    async def upload_to_gemini(
        self, file_path: str, display_name: Optional[str] = None
    ) -> Optional[genai.types.File]:
        """
        Upload a file to Gemini for analysis.

        Args:
            file_path: Path to the file to upload
            display_name: Optional display name for the file in Gemini

        Returns:
            Gemini File object if successful, None otherwise

        Raises:
            ValueError: If the file doesn't exist
            RuntimeError: If Gemini API is not configured
        """
        if not self._configured:
            raise RuntimeError(
                "Gemini API not configured. Set GEMINI_API_KEY in environment."
            )

        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"File not found: {file_path}")

        if display_name is None:
            display_name = path.name

        try:
            logger.info(f"Uploading file to Gemini: {file_path}")
            # Use asyncio.to_thread to avoid blocking the event loop
            file = await asyncio.to_thread(
                genai.upload_file, path=str(path), display_name=display_name
            )
            logger.info(
                f"File uploaded successfully: {file.name} (URI: {file.uri})"
            )
            return file
        except Exception as e:
            logger.exception(f"Failed to upload file to Gemini: {e}")
            return None

    async def upload_content_to_gemini(
        self, content: str, display_name: str = "document.txt"
    ) -> Optional[genai.types.File]:
        """
        Upload text content to Gemini by creating a temporary file.

        Args:
            content: Text content to upload
            display_name: Display name for the content in Gemini

        Returns:
            Gemini File object if successful, None otherwise

        Raises:
            RuntimeError: If Gemini API is not configured
        """
        if not self._configured:
            raise RuntimeError(
                "Gemini API not configured. Set GEMINI_API_KEY in environment."
            )

        try:
            # Create a temporary file with the content
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                delete=False,
                encoding="utf-8",
            ) as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name

            try:
                return await self.upload_to_gemini(tmp_path, display_name)
            finally:
                # Clean up temporary file
                os.unlink(tmp_path)
        except Exception as e:
            logger.exception(f"Failed to upload content to Gemini: {e}")
            return None

    async def delete_from_gemini(self, file: genai.types.File) -> bool:
        """
        Delete a file from Gemini storage.

        IMPORTANT: Always call this after classification to avoid storage costs.

        Args:
            file: Gemini File object to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        if not self._configured:
            logger.warning("Gemini API not configured, skipping file deletion")
            return False

        try:
            logger.info(f"Deleting file from Gemini: {file.name}")
            # Use asyncio.to_thread to avoid blocking the event loop
            await asyncio.to_thread(genai.delete_file, file.name)
            logger.info(f"File deleted successfully: {file.name}")
            return True
        except Exception as e:
            logger.exception(f"Failed to delete file from Gemini: {e}")
            return False

    async def classify_industry(
        self, file: genai.types.File
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Classify the industry of a document using Gemini.

        Args:
            file: Gemini File object to analyze

        Returns:
            Tuple of (industry_code, industry_name_polish) if successful,
            (None, None) otherwise

        Raises:
            RuntimeError: If Gemini API is not configured
        """
        if not self._configured:
            raise RuntimeError(
                "Gemini API not configured. Set GEMINI_API_KEY in environment."
            )

        try:
            logger.info(f"Classifying industry for file: {file.name}")

            # Create the model for classification
            model = genai.GenerativeModel("gemini-1.5-flash")

            # Generate content with the file and classification prompt
            # Use asyncio.to_thread to avoid blocking the event loop
            response = await asyncio.to_thread(
                model.generate_content, [file, CLASSIFICATION_PROMPT]
            )

            if not response or not response.text:
                logger.warning("Empty response from Gemini classification")
                return None, None

            # Parse the response to get industry code
            industry_code = response.text.strip().upper()
            logger.info(f"Gemini classification response: {industry_code}")

            # Validate the industry code
            industry = self._get_industry_by_code(industry_code)
            if industry:
                logger.info(
                    f"Industry classified: {industry['code']} - {industry['name_polish']}"
                )
                return industry["code"], industry["name_polish"]

            # Handle UNKNOWN response
            if industry_code == "UNKNOWN":
                logger.info("Industry could not be determined from document")
                return None, None

            # If code doesn't match exactly, try fuzzy matching
            industry = self._fuzzy_match_industry(response.text.strip())
            if industry:
                logger.info(
                    f"Industry fuzzy-matched: {industry['code']} - {industry['name_polish']}"
                )
                return industry["code"], industry["name_polish"]

            logger.warning(f"Unrecognized industry code: {industry_code}")
            return None, None

        except Exception as e:
            logger.exception(f"Failed to classify industry: {e}")
            return None, None

    async def classify_from_file(
        self, file_path: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Convenience method to upload, classify, and cleanup a file.

        This is the recommended method for classifying files as it handles
        the full lifecycle including cleanup.

        Args:
            file_path: Path to the file to classify

        Returns:
            Tuple of (industry_code, industry_name_polish) if successful,
            (None, None) otherwise
        """
        if not self._configured:
            logger.warning("Gemini API not configured, skipping classification")
            return None, None

        file = None
        try:
            # Upload file
            file = await self.upload_to_gemini(file_path)
            if not file:
                return None, None

            # Classify
            return await self.classify_industry(file)
        finally:
            # Always cleanup
            if file:
                await self.delete_from_gemini(file)

    async def classify_from_content(
        self, content: str, display_name: str = "document.txt"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Convenience method to classify text content.

        This is useful when you have document text but not a file.

        Args:
            content: Text content to classify
            display_name: Display name for the content

        Returns:
            Tuple of (industry_code, industry_name_polish) if successful,
            (None, None) otherwise
        """
        if not self._configured:
            logger.warning("Gemini API not configured, skipping classification")
            return None, None

        file = None
        try:
            # Upload content
            file = await self.upload_content_to_gemini(content, display_name)
            if not file:
                return None, None

            # Classify
            return await self.classify_industry(file)
        finally:
            # Always cleanup
            if file:
                await self.delete_from_gemini(file)

    def _get_industry_by_code(self, code: str) -> Optional[dict]:
        """Get industry details by code."""
        code_upper = code.upper()
        for industry in INDUSTRIES:
            if industry["code"] == code_upper:
                return industry
        return None

    def _fuzzy_match_industry(self, text: str) -> Optional[dict]:
        """
        Attempt to fuzzy match industry from response text.

        Handles cases where Gemini returns the full industry name
        instead of just the code.
        """
        text_lower = text.lower()

        for industry in INDUSTRIES:
            # Check if the Polish or English name is in the response
            if industry["name_polish"].lower() in text_lower:
                return industry
            if industry["name_english"].lower() in text_lower:
                return industry
            # Check if the code appears anywhere in the response
            if industry["code"].lower() in text_lower:
                return industry

        return None

    def get_all_industries(self) -> list:
        """Get all available industry classifications."""
        return INDUSTRIES.copy()

    def get_industry_by_polish_name(self, name_polish: str) -> Optional[dict]:
        """Get industry details by Polish name."""
        for industry in INDUSTRIES:
            if industry["name_polish"].lower() == name_polish.lower():
                return industry
        return None


# Singleton instance for convenience
_classifier_instance: Optional[IndustryClassifier] = None


def get_industry_classifier() -> IndustryClassifier:
    """
    Get the singleton IndustryClassifier instance.

    Returns:
        The IndustryClassifier singleton instance
    """
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IndustryClassifier()
    return _classifier_instance
