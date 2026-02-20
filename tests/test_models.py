"""Unit tests for Pydantic models."""

import pytest
from datetime import datetime
from src.api.models import TaxOffice, Region, Industry


@pytest.mark.unit
def test_tax_office_model_validation():
    """Test TaxOffice model creates valid instance with required fields."""
    tax_office = TaxOffice(
        kodjednostki=1001,
        nazwa_urzedu="Urząd Skarbowy Warszawa-Mokotów",
        typ="US",
        wojewodztwo="mazowieckie",
        miasto="Warszawa",
        ulica="Rakowiecka",
        nr_budynku="25",
        kod_pocztowy="00-000",
        telefon="22-123-4567",
        email="test@us.gov.pl",
        adres_bip="http://bip.example.com"
    )

    assert tax_office.kodjednostki == 1001
    assert tax_office.nazwa_urzedu == "Urząd Skarbowy Warszawa-Mokotów"
    assert tax_office.typ == "US"
    assert tax_office.wojewodztwo == "mazowieckie"


@pytest.mark.unit
def test_tax_office_model_with_id():
    """Test TaxOffice model handles _id field correctly."""
    tax_office = TaxOffice(
        id="507f1f77bcf86cd799439011",
        kodjednostki=1001,
        nazwa_urzedu="Test Office",
        typ="US",
        wojewodztwo="mazowieckie",
        miasto="Warszawa",
        ulica="Test",
        nr_budynku="1",
        kod_pocztowy="00-000",
        telefon="123456789",
        email="test@test.pl",
        adres_bip="http://test.com"
    )

    assert tax_office.id == "507f1f77bcf86cd799439011"


@pytest.mark.unit
def test_region_model_validation():
    """Test Region model creates valid instance."""
    region = Region(
        name="mazowieckie",
        display_name="Mazowieckie"
    )

    assert region.name == "mazowieckie"
    assert region.display_name == "Mazowieckie"


@pytest.mark.unit
def test_industry_model_validation():
    """Test Industry model creates valid instance."""
    industry = Industry(
        name_polish="Branża IT",
        name_english="IT",
        code="it"
    )

    assert industry.name_polish == "Branża IT"
    assert industry.name_english == "IT"
    assert industry.code == "it"


@pytest.mark.unit
def test_tax_office_missing_required_fields():
    """Test TaxOffice model raises validation error for missing required fields."""
    with pytest.raises(ValueError):
        TaxOffice(
            kodjednostki=1001,
            nazwa_urzedu="Test"
            # Missing other required fields
        )
