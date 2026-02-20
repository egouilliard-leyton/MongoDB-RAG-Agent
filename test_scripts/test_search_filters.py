"""
Test script for verifying search filtering with industry, tax office, and region.

Tests the extended search filters added in CR-MVP-13.
Includes integration tests for combined filter scenarios.
"""

import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from src.tools import build_metadata_filter


class TestBuildMetadataFilter:
    """Test cases for build_metadata_filter function."""

    def test_empty_filter(self):
        """Test that empty parameters return empty filter."""
        result = build_metadata_filter()
        assert result == {}

    def test_industry_filter(self):
        """Test industry filter is correctly applied."""
        result = build_metadata_filter(industry="IT")
        assert result == {"metadata.industry": "IT"}

    def test_tax_office_id_filter(self):
        """Test tax_office_id filter is correctly applied."""
        result = build_metadata_filter(tax_office_id=12345)
        assert result == {"metadata.tax_office_id": 12345}

    def test_region_filter(self):
        """Test region filter is correctly applied."""
        result = build_metadata_filter(region="mazowieckie")
        assert result == {"metadata.region": "mazowieckie"}

    def test_combined_new_filters(self):
        """Test combining all new filters (industry + tax_office + region)."""
        result = build_metadata_filter(
            industry="Construction",
            tax_office_id=98765,
            region="śląskie"
        )
        expected = {
            "metadata.industry": "Construction",
            "metadata.tax_office_id": 98765,
            "metadata.region": "śląskie"
        }
        assert result == expected

    def test_combined_all_filters(self):
        """Test combining new filters with existing filters."""
        result = build_metadata_filter(
            project_id="507f1f77bcf86cd799439011",
            document_type="KDIP2",
            author="DK",
            industry="Automotive",
            tax_office_id=54321,
            region="wielkopolskie",
            section_type="interpretation"
        )

        # Check all filters are present
        assert "metadata.project_id" in result
        assert result["metadata.document_type"] == "KDIP2"
        assert result["metadata.author"] == "DK"
        assert result["metadata.industry"] == "Automotive"
        assert result["metadata.tax_office_id"] == 54321
        assert result["metadata.region"] == "wielkopolskie"
        assert result["metadata.section_type"] == "interpretation"

    def test_tax_office_id_zero(self):
        """Test tax_office_id with value 0 is correctly applied (not skipped)."""
        result = build_metadata_filter(tax_office_id=0)
        assert result == {"metadata.tax_office_id": 0}

    def test_empty_strings_not_filtered(self):
        """Test that empty strings are not added as filters."""
        result = build_metadata_filter(
            industry="",
            region=""
        )
        # Empty strings are falsy, so they shouldn't be added
        assert result == {}

    def test_none_values_not_filtered(self):
        """Test that None values are not added as filters."""
        result = build_metadata_filter(
            industry=None,
            tax_office_id=None,
            region=None
        )
        assert result == {}


class TestCombinedFilterScenarios:
    """
    Integration-style tests for combined filter scenarios.

    These tests verify that the filter building logic works correctly
    for realistic combinations of filters that would be used in production.
    """

    def test_geographic_filtering_region_only(self):
        """Test filtering by region for geographic scope."""
        result = build_metadata_filter(region="mazowieckie")

        assert result == {"metadata.region": "mazowieckie"}

    def test_geographic_filtering_tax_office_only(self):
        """Test filtering by tax office for specific office scope."""
        result = build_metadata_filter(tax_office_id=101)

        assert result == {"metadata.tax_office_id": 101}

    def test_geographic_filtering_region_and_tax_office(self):
        """Test filtering by both region and tax office."""
        result = build_metadata_filter(
            region="śląskie",
            tax_office_id=305
        )

        assert result == {
            "metadata.region": "śląskie",
            "metadata.tax_office_id": 305
        }

    def test_industry_scoping_single_industry(self):
        """Test filtering by single industry."""
        result = build_metadata_filter(industry="Branża IT")

        assert result == {"metadata.industry": "Branża IT"}

    def test_full_scope_filtering(self):
        """Test filtering by industry, region, and tax office simultaneously."""
        result = build_metadata_filter(
            industry="Branża budowlana",
            region="dolnośląskie",
            tax_office_id=402
        )

        expected = {
            "metadata.industry": "Branża budowlana",
            "metadata.region": "dolnośląskie",
            "metadata.tax_office_id": 402
        }
        assert result == expected

    def test_project_scoped_with_industry(self):
        """Test project-scoped search with industry filter."""
        project_id = "507f1f77bcf86cd799439011"
        result = build_metadata_filter(
            project_id=project_id,
            industry="Branża metalurgiczna"
        )

        assert "metadata.project_id" in result
        assert result["metadata.industry"] == "Branża metalurgiczna"

    def test_project_scoped_with_all_filters(self):
        """Test project-scoped search with all new filters."""
        project_id = "507f1f77bcf86cd799439011"
        result = build_metadata_filter(
            project_id=project_id,
            industry="Branża produkcji maszyn",
            tax_office_id=501,
            region="małopolskie",
            document_type="KDIP2"
        )

        assert "metadata.project_id" in result
        assert result["metadata.industry"] == "Branża produkcji maszyn"
        assert result["metadata.tax_office_id"] == 501
        assert result["metadata.region"] == "małopolskie"
        assert result["metadata.document_type"] == "KDIP2"

    def test_document_type_with_geographic_filters(self):
        """Test document type filter combined with geographic filters."""
        result = build_metadata_filter(
            document_type="KDIB1-3",
            region="pomorskie",
            tax_office_id=601
        )

        expected = {
            "metadata.document_type": "KDIB1-3",
            "metadata.region": "pomorskie",
            "metadata.tax_office_id": 601
        }
        assert result == expected

    def test_date_range_with_new_filters(self):
        """Test date range filtering combined with new filters."""
        result = build_metadata_filter(
            date_from="2025-01-01",
            date_to="2025-12-31",
            industry="Branża automotive",
            region="wielkopolskie"
        )

        assert "metadata.document_date" in result
        assert result["metadata.document_date"]["$gte"] == "2025-01-01"
        assert result["metadata.document_date"]["$lte"] == "2025-12-31"
        assert result["metadata.industry"] == "Branża automotive"
        assert result["metadata.region"] == "wielkopolskie"

    def test_keywords_with_new_filters(self):
        """Test keywords filtering combined with new filters."""
        result = build_metadata_filter(
            keywords=["ulga", "badanie", "rozwój"],
            industry="Branża biotechnologiczna",
            tax_office_id=702
        )

        assert result["metadata.slowa_kluczowe"] == {"$in": ["ulga", "badanie", "rozwój"]}
        assert result["metadata.industry"] == "Branża biotechnologiczna"
        assert result["metadata.tax_office_id"] == 702

    def test_all_polish_voivodeships_valid(self):
        """Test that all 16 Polish voivodeships work as region filters."""
        voivodeships = [
            "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie",
            "łódzkie", "małopolskie", "mazowieckie", "opolskie",
            "podkarpackie", "podlaskie", "pomorskie", "śląskie",
            "świętokrzyskie", "warmińsko-mazurskie", "wielkopolskie", "zachodniopomorskie"
        ]

        for voivodeship in voivodeships:
            result = build_metadata_filter(region=voivodeship)
            assert result == {"metadata.region": voivodeship}, f"Failed for {voivodeship}"

    def test_all_predefined_industries_valid(self):
        """Test that all 18+ predefined industries work as filters."""
        industries = [
            "Branża produkcji maszyn", "Branża IT", "Branża metalurgiczna",
            "Branża budowlana", "Branża spożywcza", "Branża opakowań i tworzyw sztucznych",
            "Branża meblowa", "Branża konstrukcji stalowych", "Branża tekstylna",
            "Branża kosmetyczna, farmaceutyczna, medyczna", "Branża chemiczna",
            "Branża poligraficzna", "Branża automotive", "Branża energetyczna",
            "Branża HVAC", "Branża architektoniczna", "Branża biotechnologiczna",
            "Branża recyklingowa", "Branża stoczniowa"
        ]

        for industry in industries:
            result = build_metadata_filter(industry=industry)
            assert result == {"metadata.industry": industry}, f"Failed for {industry}"

    def test_partial_filters_mixed(self):
        """Test that only provided filters are applied (partial combination)."""
        # Only industry and region (no tax_office_id)
        result = build_metadata_filter(
            industry="Branża chemiczna",
            region="śląskie"
        )

        assert result == {
            "metadata.industry": "Branża chemiczna",
            "metadata.region": "śląskie"
        }
        assert "metadata.tax_office_id" not in result

        # Only industry and tax_office_id (no region)
        result2 = build_metadata_filter(
            industry="Branża energetyczna",
            tax_office_id=801
        )

        assert result2 == {
            "metadata.industry": "Branża energetyczna",
            "metadata.tax_office_id": 801
        }
        assert "metadata.region" not in result2


class TestFilterEdgeCases:
    """Tests for edge cases in filter building."""

    def test_tax_office_id_large_values(self):
        """Test tax_office_id with large values."""
        result = build_metadata_filter(tax_office_id=999999)
        assert result == {"metadata.tax_office_id": 999999}

    def test_special_characters_in_region(self):
        """Test regions with special Polish characters."""
        # Polish regions with diacritics
        regions_with_diacritics = [
            "śląskie",
            "świętokrzyskie",
            "łódzkie",
            "małopolskie"
        ]

        for region in regions_with_diacritics:
            result = build_metadata_filter(region=region)
            assert result["metadata.region"] == region

    def test_special_characters_in_industry(self):
        """Test industries with special Polish characters."""
        industries_with_diacritics = [
            "Branża kosmetyczna, farmaceutyczna, medyczna",
            "Branża opakowań i tworzyw sztucznych"
        ]

        for industry in industries_with_diacritics:
            result = build_metadata_filter(industry=industry)
            assert result["metadata.industry"] == industry

    def test_whitespace_in_values(self):
        """Test that filters preserve whitespace in values."""
        result = build_metadata_filter(
            industry="Branża produkcji maszyn",
            region="warmińsko-mazurskie"
        )

        assert result["metadata.industry"] == "Branża produkcji maszyn"
        assert result["metadata.region"] == "warmińsko-mazurskie"

    def test_invalid_project_id_creates_impossible_filter(self):
        """Test that invalid project_id creates an ObjectId filter (graceful handling)."""
        result = build_metadata_filter(project_id="invalid-id")

        # Should still create a filter (with a new ObjectId to prevent data leakage)
        assert "metadata.project_id" in result

    def test_empty_keywords_list(self):
        """Test that empty keywords list doesn't create filter."""
        result = build_metadata_filter(
            keywords=[],
            industry="Branża IT"
        )

        # Empty list is falsy, shouldn't add keywords filter
        assert "metadata.slowa_kluczowe" not in result
        assert result["metadata.industry"] == "Branża IT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
