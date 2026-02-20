"""Tax office API endpoints for managing Polish tax office reference data."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.api.models import TaxOffice
from src.api.exceptions import NotFoundError, ValidationError
from src.settings import load_settings
from src.services.tax_office_storage import TaxOfficeStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tax-offices", tags=["tax-offices"])


@router.get("", response_model=List[TaxOffice])
async def list_tax_offices(
    limit: int = Query(default=100, ge=1, le=600, description="Maximum number of results"),
    skip: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> List[TaxOffice]:
    """
    List all tax offices with pagination.

    Args:
        limit: Maximum number of results (default: 100, max: 600)
        skip: Number of results to skip for pagination (default: 0)

    Returns:
        List of tax office records sorted by name
    """
    settings = load_settings()
    svc = TaxOfficeStorageService(settings)
    await svc.initialize()
    try:
        tax_offices = await svc.list_tax_offices(limit=limit, skip=skip)
        return [TaxOffice(**office) for office in tax_offices]
    finally:
        await svc.cleanup()


@router.get("/search", response_model=List[TaxOffice])
async def search_tax_offices(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of results"),
) -> List[TaxOffice]:
    """
    Search tax offices by name, city, or kodjednostki ID.

    Uses case-insensitive regex matching on office name (nazwa_urzedu) and city (miasto).
    If the query is numeric, also matches against the kodjednostki (tax office ID).

    Args:
        q: Search query string
        limit: Maximum number of results (default: 20, max: 100)

    Returns:
        List of matching tax office records sorted by name
    """
    settings = load_settings()
    svc = TaxOfficeStorageService(settings)
    await svc.initialize()
    try:
        tax_offices = await svc.search_tax_offices(query=q, limit=limit)
        return [TaxOffice(**office) for office in tax_offices]
    finally:
        await svc.cleanup()


@router.get("/regions", response_model=Dict[str, List[TaxOffice]])
async def list_tax_offices_by_region() -> Dict[str, List[TaxOffice]]:
    """
    List all tax offices grouped by region (voivodeship).

    Returns:
        Dictionary mapping region names to lists of tax offices in that region
    """
    settings = load_settings()
    svc = TaxOfficeStorageService(settings)
    await svc.initialize()
    try:
        grouped = await svc.get_tax_offices_grouped_by_region()
        # Convert inner documents to TaxOffice models
        result: Dict[str, List[TaxOffice]] = {}
        for region, offices in grouped.items():
            result[region] = [TaxOffice(**office) for office in offices]
        return result
    finally:
        await svc.cleanup()


@router.get("/count")
async def count_tax_offices() -> Dict[str, int]:
    """
    Get total count of tax offices.

    Returns:
        Dictionary with total count of tax offices
    """
    settings = load_settings()
    svc = TaxOfficeStorageService(settings)
    await svc.initialize()
    try:
        count = await svc.count_tax_offices()
        return {"count": count}
    finally:
        await svc.cleanup()


@router.get("/{kodjednostki}", response_model=TaxOffice)
async def get_tax_office(kodjednostki: int) -> TaxOffice:
    """
    Get a tax office by its kodjednostki (unique ID).

    Args:
        kodjednostki: Tax office unique identifier

    Returns:
        Tax office record

    Raises:
        NotFoundError: If tax office with given ID is not found
    """
    if kodjednostki <= 0:
        raise ValidationError("kodjednostki must be a positive integer")

    settings = load_settings()
    svc = TaxOfficeStorageService(settings)
    await svc.initialize()
    try:
        tax_office = await svc.get_tax_office_by_id(kodjednostki)
        if not tax_office:
            raise NotFoundError("Tax office", str(kodjednostki))
        return TaxOffice(**tax_office)
    finally:
        await svc.cleanup()
