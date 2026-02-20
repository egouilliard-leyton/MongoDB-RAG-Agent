"""Unit tests for IndustryClassifier service with mocked Gemini API."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

from src.services.industry_classifier import (
    IndustryClassifier,
    INDUSTRIES,
    CLASSIFICATION_PROMPT,
)


class TestIndustryClassifierInit:
    """Tests for IndustryClassifier initialization."""

    @patch("src.services.industry_classifier.load_settings")
    def test_init_without_api_key(self, mock_load_settings: MagicMock) -> None:
        """Test initialization when Gemini API key is not configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()

        assert classifier.is_available is False

    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    def test_init_with_api_key(
        self, mock_load_settings: MagicMock, mock_genai: MagicMock
    ) -> None:
        """Test initialization when Gemini API key is configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-api-key"
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()

        assert classifier.is_available is True
        mock_genai.configure.assert_called_once_with(api_key="test-api-key")


class TestIndustryClassifierIndustries:
    """Tests for industry list and lookup methods."""

    @patch("src.services.industry_classifier.load_settings")
    def test_get_all_industries(self, mock_load_settings: MagicMock) -> None:
        """Test getting all available industries."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        industries = classifier.get_all_industries()

        assert len(industries) == 19  # Updated from 18 based on service
        assert all("code" in industry for industry in industries)
        assert all("name_polish" in industry for industry in industries)
        assert all("name_english" in industry for industry in industries)

    @patch("src.services.industry_classifier.load_settings")
    def test_get_industry_by_code_valid(self, mock_load_settings: MagicMock) -> None:
        """Test getting industry by valid code."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        industry = classifier._get_industry_by_code("IT")

        assert industry is not None
        assert industry["code"] == "IT"
        assert industry["name_english"] == "IT"

    @patch("src.services.industry_classifier.load_settings")
    def test_get_industry_by_code_case_insensitive(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test getting industry by code is case insensitive."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()

        industry_lower = classifier._get_industry_by_code("it")
        industry_upper = classifier._get_industry_by_code("IT")
        industry_mixed = classifier._get_industry_by_code("It")

        assert industry_lower == industry_upper == industry_mixed
        assert industry_lower is not None

    @patch("src.services.industry_classifier.load_settings")
    def test_get_industry_by_code_invalid(self, mock_load_settings: MagicMock) -> None:
        """Test getting industry by invalid code returns None."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        industry = classifier._get_industry_by_code("INVALID_CODE")

        assert industry is None

    @patch("src.services.industry_classifier.load_settings")
    def test_get_industry_by_polish_name(self, mock_load_settings: MagicMock) -> None:
        """Test getting industry by Polish name."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        industry = classifier.get_industry_by_polish_name("Branża IT")

        assert industry is not None
        assert industry["code"] == "IT"

    @patch("src.services.industry_classifier.load_settings")
    def test_get_industry_by_polish_name_case_insensitive(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test getting industry by Polish name is case insensitive."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        industry = classifier.get_industry_by_polish_name("branża it")

        assert industry is not None
        assert industry["code"] == "IT"


class TestIndustryClassifierFuzzyMatch:
    """Tests for fuzzy matching functionality."""

    @patch("src.services.industry_classifier.load_settings")
    def test_fuzzy_match_by_code_in_response(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test fuzzy matching when code appears in response."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        result = classifier._fuzzy_match_industry("The industry is IT based on content")

        assert result is not None
        assert result["code"] == "IT"

    @patch("src.services.industry_classifier.load_settings")
    def test_fuzzy_match_by_polish_name(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test fuzzy matching when Polish name appears in response."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        result = classifier._fuzzy_match_industry(
            "The company belongs to Branża budowlana sector"
        )

        assert result is not None
        assert result["code"] == "CONSTRUCTION"

    @patch("src.services.industry_classifier.load_settings")
    def test_fuzzy_match_by_english_name(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test fuzzy matching when English name appears in response."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        result = classifier._fuzzy_match_industry(
            "This is a Construction company"
        )

        assert result is not None
        assert result["code"] == "CONSTRUCTION"

    @patch("src.services.industry_classifier.load_settings")
    def test_fuzzy_match_no_match(self, mock_load_settings: MagicMock) -> None:
        """Test fuzzy matching returns None when no match found."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        # Use text that won't accidentally match any industry codes or names
        result = classifier._fuzzy_match_industry("The result is unclear, no specific sector")

        assert result is None


class TestIndustryClassifierUpload:
    """Tests for file upload functionality."""

    @patch("src.services.industry_classifier.load_settings")
    def test_upload_to_gemini_not_configured(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test upload raises error when API not configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()

        with pytest.raises(RuntimeError) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                classifier.upload_to_gemini("/path/to/file.pdf")
            )

        assert "Gemini API not configured" in str(exc_info.value)

    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    def test_upload_to_gemini_file_not_found(
        self, mock_load_settings: MagicMock, mock_genai: MagicMock
    ) -> None:
        """Test upload raises error when file doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()

        with pytest.raises(ValueError) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                classifier.upload_to_gemini("/nonexistent/file.pdf")
            )

        assert "File not found" in str(exc_info.value)


class TestIndustryClassifierClassification:
    """Tests for classification functionality with mocks."""

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.asyncio.to_thread")
    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_industry_returns_valid_code(
        self,
        mock_load_settings: MagicMock,
        mock_genai: MagicMock,
        mock_to_thread: MagicMock
    ) -> None:
        """Test classification returns valid industry code."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_load_settings.return_value = mock_settings

        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.text = "IT"
        mock_to_thread.return_value = mock_response

        # Mock file
        mock_file = MagicMock()
        mock_file.name = "test-file"

        classifier = IndustryClassifier()
        code, name = await classifier.classify_industry(mock_file)

        assert code == "IT"
        assert name == "Branża IT"

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.asyncio.to_thread")
    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_industry_handles_unknown_response(
        self,
        mock_load_settings: MagicMock,
        mock_genai: MagicMock,
        mock_to_thread: MagicMock
    ) -> None:
        """Test classification handles UNKNOWN response."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_load_settings.return_value = mock_settings

        # Mock Gemini response with UNKNOWN
        mock_response = MagicMock()
        mock_response.text = "UNKNOWN"
        mock_to_thread.return_value = mock_response

        mock_file = MagicMock()
        mock_file.name = "test-file"

        classifier = IndustryClassifier()
        code, name = await classifier.classify_industry(mock_file)

        assert code is None
        assert name is None

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.asyncio.to_thread")
    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_industry_handles_empty_response(
        self,
        mock_load_settings: MagicMock,
        mock_genai: MagicMock,
        mock_to_thread: MagicMock
    ) -> None:
        """Test classification handles empty response."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_load_settings.return_value = mock_settings

        # Mock empty Gemini response
        mock_response = MagicMock()
        mock_response.text = ""
        mock_to_thread.return_value = mock_response

        mock_file = MagicMock()
        mock_file.name = "test-file"

        classifier = IndustryClassifier()
        code, name = await classifier.classify_industry(mock_file)

        assert code is None
        assert name is None

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.asyncio.to_thread")
    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_industry_fuzzy_matches_full_response(
        self,
        mock_load_settings: MagicMock,
        mock_genai: MagicMock,
        mock_to_thread: MagicMock
    ) -> None:
        """Test classification fuzzy matches when response contains full industry name."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_load_settings.return_value = mock_settings

        # Mock Gemini response with full name instead of code
        mock_response = MagicMock()
        mock_response.text = "Based on the document, this is a Construction company"
        mock_to_thread.return_value = mock_response

        mock_file = MagicMock()
        mock_file.name = "test-file"

        classifier = IndustryClassifier()
        code, name = await classifier.classify_industry(mock_file)

        assert code == "CONSTRUCTION"
        assert name == "Branża budowlana"

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_industry_not_configured(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test classification raises error when not configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        mock_file = MagicMock()

        classifier = IndustryClassifier()

        with pytest.raises(RuntimeError) as exc_info:
            await classifier.classify_industry(mock_file)

        assert "Gemini API not configured" in str(exc_info.value)


class TestIndustryClassifierDelete:
    """Tests for file deletion functionality."""

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.asyncio.to_thread")
    @patch("src.services.industry_classifier.genai")
    @patch("src.services.industry_classifier.load_settings")
    async def test_delete_from_gemini_success(
        self,
        mock_load_settings: MagicMock,
        mock_genai: MagicMock,
        mock_to_thread: MagicMock
    ) -> None:
        """Test successful file deletion from Gemini."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test-key"
        mock_load_settings.return_value = mock_settings

        mock_to_thread.return_value = None

        mock_file = MagicMock()
        mock_file.name = "test-file"

        classifier = IndustryClassifier()
        result = await classifier.delete_from_gemini(mock_file)

        assert result is True
        mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.load_settings")
    async def test_delete_from_gemini_not_configured(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test deletion returns False when not configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        mock_file = MagicMock()

        classifier = IndustryClassifier()
        result = await classifier.delete_from_gemini(mock_file)

        assert result is False


class TestIndustryClassifierConvenienceMethods:
    """Tests for convenience methods that handle full workflow."""

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_from_file_not_configured(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test classify_from_file returns None when not configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        code, name = await classifier.classify_from_file("/path/to/file.pdf")

        assert code is None
        assert name is None

    @pytest.mark.asyncio
    @patch("src.services.industry_classifier.load_settings")
    async def test_classify_from_content_not_configured(
        self, mock_load_settings: MagicMock
    ) -> None:
        """Test classify_from_content returns None when not configured."""
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_load_settings.return_value = mock_settings

        classifier = IndustryClassifier()
        code, name = await classifier.classify_from_content("Sample document content")

        assert code is None
        assert name is None


class TestIndustryConstants:
    """Tests for industry constants and configuration."""

    def test_industries_list_structure(self) -> None:
        """Test that INDUSTRIES list has correct structure."""
        assert len(INDUSTRIES) > 0

        for industry in INDUSTRIES:
            assert "code" in industry
            assert "name_polish" in industry
            assert "name_english" in industry
            assert isinstance(industry["code"], str)
            assert industry["code"] == industry["code"].upper()

    def test_all_industry_codes_unique(self) -> None:
        """Test that all industry codes are unique."""
        codes = [industry["code"] for industry in INDUSTRIES]
        assert len(codes) == len(set(codes))

    def test_classification_prompt_exists(self) -> None:
        """Test that classification prompt is defined and contains key elements."""
        assert len(CLASSIFICATION_PROMPT) > 0
        assert "INDUSTRY OPTIONS" in CLASSIFICATION_PROMPT
        assert "UNKNOWN" in CLASSIFICATION_PROMPT

    def test_expected_industries_present(self) -> None:
        """Test that expected industries are present."""
        codes = {industry["code"] for industry in INDUSTRIES}
        expected_codes = {
            "IT", "CONSTRUCTION", "AUTOMOTIVE", "MACHINERY", "FOOD",
            "PHARMA", "CHEMICAL", "ENERGY", "HVAC", "BIOTECH"
        }
        assert expected_codes.issubset(codes)


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
