"""Region API endpoints for managing Polish voivodeship reference data."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Path
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from src.api.models import Region, TaxOffice
from src.api.exceptions import NotFoundError
from src.settings import load_settings
from src.services.tax_office_storage import TaxOfficeStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/regions", tags=["regions"])


# List of 16 Polish voivodeships (regions)
POLISH_REGIONS: List[Dict[str, str]] = [
    {"name": "dolnośląskie", "display_name": "Dolnośląskie"},
    {"name": "kujawsko-pomorskie", "display_name": "Kujawsko-Pomorskie"},
    {"name": "lubelskie", "display_name": "Lubelskie"},
    {"name": "lubuskie", "display_name": "Lubuskie"},
    {"name": "łódzkie", "display_name": "Łódzkie"},
    {"name": "małopolskie", "display_name": "Małopolskie"},
    {"name": "mazowieckie", "display_name": "Mazowieckie"},
    {"name": "opolskie", "display_name": "Opolskie"},
    {"name": "podkarpackie", "display_name": "Podkarpackie"},
    {"name": "podlaskie", "display_name": "Podlaskie"},
    {"name": "pomorskie", "display_name": "Pomorskie"},
    {"name": "śląskie", "display_name": "Śląskie"},
    {"name": "świętokrzyskie", "display_name": "Świętokrzyskie"},
    {"name": "warmińsko-mazurskie", "display_name": "Warmińsko-Mazurskie"},
    {"name": "wielkopolskie", "display_name": "Wielkopolskie"},
    {"name": "zachodniopomorskie", "display_name": "Zachodniopomorskie"},
]

# Valid region names for validation
VALID_REGION_NAMES: set[str] = {r["name"] for r in POLISH_REGIONS}


@router.get("", response_model=List[Region])
async def list_regions() -> List[Region]:
    """
    List all 16 Polish regions (voivodeships).

    Returns:
        List of all Polish voivodeships sorted alphabetically
    """
    # Check if regions are stored in MongoDB, otherwise return the static list
    settings = load_settings()

    try:
        mongo_client: AsyncMongoClient[Dict[str, Any]] = AsyncMongoClient(
            settings.mongodb_uri, serverSelectionTimeoutMS=5000
        )
        db: AsyncDatabase[Dict[str, Any]] = mongo_client[settings.mongodb_database]

        try:
            # Try to fetch from database first
            collection = db[settings.mongodb_collection_regions]
            count = await collection.count_documents({})

            if count > 0:
                # Return from database if populated
                regions: List[Region] = []
                cursor = collection.find().sort("name", 1)
                async for doc in cursor:
                    doc["_id"] = str(doc["_id"])
                    regions.append(Region(**doc))
                return regions
        finally:
            await mongo_client.close()
    except Exception as e:
        logger.warning(f"Could not fetch regions from database, using static list: {e}")

    # Return static list if database not available or empty
    return [
        Region(name=r["name"], display_name=r["display_name"])
        for r in POLISH_REGIONS
    ]


@router.get("/{name}/tax-offices", response_model=List[TaxOffice])
async def get_tax_offices_by_region(
    name: str = Path(
        ...,
        min_length=1,
        max_length=50,
        description="Region name (voivodeship)"
    )
) -> List[TaxOffice]:
    """
    Get all tax offices in a specific region (voivodeship).

    Args:
        name: Region name (must be one of the 16 Polish voivodeships)

    Returns:
        List of tax offices in the specified region

    Raises:
        NotFoundError: If region name is not valid
    """
    # Normalize region name (lowercase for comparison)
    normalized_name = name.lower().strip()

    # Validate region name
    if normalized_name not in VALID_REGION_NAMES:
        raise NotFoundError(
            "Region",
            f"{name}. Valid regions: {', '.join(sorted(VALID_REGION_NAMES))}"
        )

    settings = load_settings()
    svc = TaxOfficeStorageService(settings)
    await svc.initialize()

    try:
        # Use normalized name to query tax offices
        tax_offices = await svc.get_tax_offices_by_region(normalized_name)
        return [TaxOffice(**office) for office in tax_offices]
    finally:
        await svc.cleanup()


@router.get("/count")
async def count_regions() -> Dict[str, int]:
    """
    Get total count of regions.

    Returns:
        Dictionary with total count of regions (always 16)
    """
    return {"count": len(POLISH_REGIONS)}
