"""Industry API endpoints for managing industry reference data."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from src.api.models import Industry
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/industries", tags=["industries"])


# List of 19 predefined industries from client requirements
INDUSTRIES: List[Dict[str, str]] = [
    {
        "code": "machinery",
        "name_polish": "Branża produkcji maszyn",
        "name_english": "Machinery production",
    },
    {
        "code": "it",
        "name_polish": "Branża IT",
        "name_english": "IT",
    },
    {
        "code": "metallurgical",
        "name_polish": "Branża metalurgiczna",
        "name_english": "Metallurgical",
    },
    {
        "code": "construction",
        "name_polish": "Branża budowlana",
        "name_english": "Construction",
    },
    {
        "code": "food",
        "name_polish": "Branża spożywcza",
        "name_english": "Food",
    },
    {
        "code": "packaging_plastics",
        "name_polish": "Branża opakowań i tworzyw sztucznych",
        "name_english": "Packaging & plastics",
    },
    {
        "code": "furniture",
        "name_polish": "Branża meblowa",
        "name_english": "Furniture",
    },
    {
        "code": "steel_construction",
        "name_polish": "Branża konstrukcji stalowych",
        "name_english": "Steel construction",
    },
    {
        "code": "textile",
        "name_polish": "Branża tekstylna",
        "name_english": "Textile",
    },
    {
        "code": "cosmetic_pharma_medical",
        "name_polish": "Branża kosmetyczna, farmaceutyczna, medyczna",
        "name_english": "Cosmetic, pharmaceutical, medical",
    },
    {
        "code": "chemical",
        "name_polish": "Branża chemiczna",
        "name_english": "Chemical",
    },
    {
        "code": "printing",
        "name_polish": "Branża poligraficzna",
        "name_english": "Printing",
    },
    {
        "code": "automotive",
        "name_polish": "Branża automotive",
        "name_english": "Automotive",
    },
    {
        "code": "energy",
        "name_polish": "Branża energetyczna",
        "name_english": "Energy",
    },
    {
        "code": "hvac",
        "name_polish": "Branża HVAC",
        "name_english": "HVAC",
    },
    {
        "code": "architectural",
        "name_polish": "Branża architektoniczna",
        "name_english": "Architectural",
    },
    {
        "code": "biotechnology",
        "name_polish": "Branża biotechnologiczna",
        "name_english": "Biotechnology",
    },
    {
        "code": "recycling",
        "name_polish": "Branża recyklingowa",
        "name_english": "Recycling",
    },
    {
        "code": "shipyard",
        "name_polish": "Branża stoczniowa",
        "name_english": "Shipyard",
    },
]

# Valid industry codes for validation
VALID_INDUSTRY_CODES: set[str] = {i["code"] for i in INDUSTRIES}


@router.get("", response_model=List[Industry])
async def list_industries() -> List[Industry]:
    """
    List all 19 industries.

    Returns:
        List of all predefined industries sorted alphabetically by English name
    """
    # Check if industries are stored in MongoDB, otherwise return the static list
    settings = load_settings()

    try:
        mongo_client: AsyncMongoClient[Dict[str, Any]] = AsyncMongoClient(
            settings.mongodb_uri, serverSelectionTimeoutMS=5000
        )
        db: AsyncDatabase[Dict[str, Any]] = mongo_client[settings.mongodb_database]

        try:
            # Try to fetch from database first
            collection = db[settings.mongodb_collection_industries]
            count = await collection.count_documents({})

            if count > 0:
                # Return from database if populated
                industries: List[Industry] = []
                cursor = collection.find().sort("name_english", 1)
                async for doc in cursor:
                    doc["_id"] = str(doc["_id"])
                    industries.append(Industry(**doc))
                return industries
        finally:
            await mongo_client.close()
    except Exception as e:
        logger.warning(f"Could not fetch industries from database, using static list: {e}")

    # Return static list if database not available or empty
    return [
        Industry(
            code=i["code"],
            name_polish=i["name_polish"],
            name_english=i["name_english"],
        )
        for i in sorted(INDUSTRIES, key=lambda x: x["name_english"])
    ]


@router.get("/count")
async def count_industries() -> Dict[str, int]:
    """
    Get total count of industries.

    Returns:
        Dictionary with total count of industries (always 19)
    """
    return {"count": len(INDUSTRIES)}
