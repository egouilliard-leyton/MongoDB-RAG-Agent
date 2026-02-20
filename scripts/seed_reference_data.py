#!/usr/bin/env python3
"""Seed industry and region reference data into MongoDB.

This script creates the reference data collections for:
- 19 predefined industries (with Polish and English names)
- 16 Polish voivodeships (regions)

Usage:
    python scripts/seed_reference_data.py
    python scripts/seed_reference_data.py --dry-run
    python scripts/seed_reference_data.py --clear-existing
    python scripts/seed_reference_data.py --verify-only
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from pymongo import AsyncMongoClient
from pymongo.errors import BulkWriteError, ConnectionFailure

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.settings import load_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 18 Industries from client specification
INDUSTRIES: List[Dict[str, str]] = [
    {
        "name_polish": "Branża produkcji maszyn",
        "name_english": "Machinery production",
        "code": "MACHINERY",
    },
    {
        "name_polish": "Branża IT",
        "name_english": "IT",
        "code": "IT",
    },
    {
        "name_polish": "Branża metalurgiczna",
        "name_english": "Metallurgical",
        "code": "METALLURGICAL",
    },
    {
        "name_polish": "Branża budowlana",
        "name_english": "Construction",
        "code": "CONSTRUCTION",
    },
    {
        "name_polish": "Branża spożywcza",
        "name_english": "Food",
        "code": "FOOD",
    },
    {
        "name_polish": "Branża opakowań i tworzyw sztucznych",
        "name_english": "Packaging & plastics",
        "code": "PACKAGING_PLASTICS",
    },
    {
        "name_polish": "Branża meblowa",
        "name_english": "Furniture",
        "code": "FURNITURE",
    },
    {
        "name_polish": "Branża konstrukcji stalowych",
        "name_english": "Steel construction",
        "code": "STEEL_CONSTRUCTION",
    },
    {
        "name_polish": "Branża tekstylna",
        "name_english": "Textile",
        "code": "TEXTILE",
    },
    {
        "name_polish": "Branża kosmetyczna, farmaceutyczna, medyczna",
        "name_english": "Cosmetic, pharmaceutical, medical",
        "code": "COSMETIC_PHARMA_MEDICAL",
    },
    {
        "name_polish": "Branża chemiczna",
        "name_english": "Chemical",
        "code": "CHEMICAL",
    },
    {
        "name_polish": "Branża poligraficzna",
        "name_english": "Printing",
        "code": "PRINTING",
    },
    {
        "name_polish": "Branża automotive",
        "name_english": "Automotive",
        "code": "AUTOMOTIVE",
    },
    {
        "name_polish": "Branża energetyczna",
        "name_english": "Energy",
        "code": "ENERGY",
    },
    {
        "name_polish": "Branża HVAC",
        "name_english": "HVAC",
        "code": "HVAC",
    },
    {
        "name_polish": "Branża architektoniczna",
        "name_english": "Architectural",
        "code": "ARCHITECTURAL",
    },
    {
        "name_polish": "Branża biotechnologiczna",
        "name_english": "Biotechnology",
        "code": "BIOTECHNOLOGY",
    },
    {
        "name_polish": "Branża recyklingowa",
        "name_english": "Recycling",
        "code": "RECYCLING",
    },
    {
        "name_polish": "Branża stoczniowa",
        "name_english": "Shipyard",
        "code": "SHIPYARD",
    },
]

# 16 Polish Voivodeships (Regions)
REGIONS: List[Dict[str, str]] = [
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


async def seed_industries(
    client: AsyncMongoClient[Dict[str, Any]],
    database: str,
    collection_name: str,
    dry_run: bool = False,
    clear_existing: bool = False,
) -> int:
    """
    Seed industry reference data into MongoDB.

    Args:
        client: MongoDB async client
        database: Database name
        collection_name: Collection name for industries
        dry_run: If True, validate data but don't insert
        clear_existing: If True, clear existing data before insert

    Returns:
        Number of records inserted
    """
    logger.info("Seeding industries...")

    if dry_run:
        logger.info(f"DRY RUN - Would insert {len(INDUSTRIES)} industries:")
        for industry in INDUSTRIES:
            logger.info(f"  {industry['code']}: {industry['name_english']}")
        return 0

    db = client[database]
    collection = db[collection_name]

    # Clear existing data if requested
    if clear_existing:
        existing_count = await collection.count_documents({})
        if existing_count > 0:
            logger.info(f"Clearing {existing_count} existing industry documents")
            await collection.delete_many({})

    # Create indexes
    logger.info("Creating industry indexes...")
    await collection.create_index("code", unique=True)
    await collection.create_index("name_polish")
    await collection.create_index("name_english")
    logger.info("Industry indexes created")

    # Insert industries
    try:
        result = await collection.insert_many(INDUSTRIES, ordered=False)
        inserted_count = len(result.inserted_ids)
        logger.info(f"Successfully inserted {inserted_count} industries")
        return inserted_count
    except BulkWriteError as e:
        inserted_count = e.details.get("nInserted", 0)
        write_errors = e.details.get("writeErrors", [])

        # Log duplicate key errors (from re-running)
        duplicates = [err for err in write_errors if err.get("code") == 11000]
        if duplicates:
            logger.warning(f"Skipped {len(duplicates)} duplicate industries")

        logger.info(f"Inserted {inserted_count} new industries")
        return inserted_count


async def seed_regions(
    client: AsyncMongoClient[Dict[str, Any]],
    database: str,
    collection_name: str,
    dry_run: bool = False,
    clear_existing: bool = False,
) -> int:
    """
    Seed region reference data into MongoDB.

    Args:
        client: MongoDB async client
        database: Database name
        collection_name: Collection name for regions
        dry_run: If True, validate data but don't insert
        clear_existing: If True, clear existing data before insert

    Returns:
        Number of records inserted
    """
    logger.info("Seeding regions...")

    if dry_run:
        logger.info(f"DRY RUN - Would insert {len(REGIONS)} regions:")
        for region in REGIONS:
            logger.info(f"  {region['name']}: {region['display_name']}")
        return 0

    db = client[database]
    collection = db[collection_name]

    # Clear existing data if requested
    if clear_existing:
        existing_count = await collection.count_documents({})
        if existing_count > 0:
            logger.info(f"Clearing {existing_count} existing region documents")
            await collection.delete_many({})

    # Create indexes
    logger.info("Creating region indexes...")
    await collection.create_index("name", unique=True)
    await collection.create_index("display_name")
    logger.info("Region indexes created")

    # Insert regions
    try:
        result = await collection.insert_many(REGIONS, ordered=False)
        inserted_count = len(result.inserted_ids)
        logger.info(f"Successfully inserted {inserted_count} regions")
        return inserted_count
    except BulkWriteError as e:
        inserted_count = e.details.get("nInserted", 0)
        write_errors = e.details.get("writeErrors", [])

        # Log duplicate key errors (from re-running)
        duplicates = [err for err in write_errors if err.get("code") == 11000]
        if duplicates:
            logger.warning(f"Skipped {len(duplicates)} duplicate regions")

        logger.info(f"Inserted {inserted_count} new regions")
        return inserted_count


async def seed_all(
    dry_run: bool = False,
    clear_existing: bool = False,
) -> Dict[str, int]:
    """
    Seed all reference data (industries and regions).

    Args:
        dry_run: If True, validate data but don't insert
        clear_existing: If True, clear existing data before insert

    Returns:
        Dictionary with counts for each collection
    """
    settings = load_settings()

    logger.info(f"Connecting to MongoDB: {settings.mongodb_database}")
    client: AsyncMongoClient[Dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=10000
    )

    try:
        # Verify connection
        await client.admin.command("ping")
        logger.info("MongoDB connection successful")

        # Seed industries
        industry_count = await seed_industries(
            client=client,
            database=settings.mongodb_database,
            collection_name=settings.mongodb_collection_industries,
            dry_run=dry_run,
            clear_existing=clear_existing,
        )

        # Seed regions
        region_count = await seed_regions(
            client=client,
            database=settings.mongodb_database,
            collection_name=settings.mongodb_collection_regions,
            dry_run=dry_run,
            clear_existing=clear_existing,
        )

        return {
            "industries": industry_count,
            "regions": region_count,
        }

    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    finally:
        await client.close()


async def verify_seed() -> None:
    """Verify the seed by checking document counts and sample data."""
    settings = load_settings()

    client: AsyncMongoClient[Dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=10000
    )

    try:
        await client.admin.command("ping")
        db = client[settings.mongodb_database]

        # Verify industries
        industries_collection = db[settings.mongodb_collection_industries]
        industry_count = await industries_collection.count_documents({})
        logger.info(f"\nIndustries in database: {industry_count}")

        if industry_count > 0:
            logger.info("Sample industries:")
            cursor = industries_collection.find().limit(5)
            async for doc in cursor:
                logger.info(f"  [{doc['code']}] {doc['name_english']} / {doc['name_polish']}")

        if industry_count == 19:  # 19 predefined industries from client list
            logger.info(f"✓ Industries: Expected 19, found {industry_count}")
        else:
            logger.warning(f"⚠ Industries: Expected 19, found {industry_count}")

        # Verify regions
        regions_collection = db[settings.mongodb_collection_regions]
        region_count = await regions_collection.count_documents({})
        logger.info(f"\nRegions in database: {region_count}")

        if region_count > 0:
            logger.info("All regions:")
            cursor = regions_collection.find().sort("name", 1)
            async for doc in cursor:
                logger.info(f"  {doc['display_name']} ({doc['name']})")

        if region_count == 16:
            logger.info(f"\n✓ Regions: Expected 16, found {region_count}")
        else:
            logger.warning(f"\n⚠ Regions: Expected 16, found {region_count}")

        # Overall verification
        if industry_count == 19 and region_count == 16:
            logger.info("\n✓ Verification PASSED: All reference data seeded correctly")
        else:
            logger.warning("\n⚠ Verification WARNING: Some data may be missing")

    finally:
        await client.close()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed industry and region reference data into MongoDB"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data without inserting into database",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing reference data before seeding",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing data without seeding",
    )

    args = parser.parse_args()

    if args.verify_only:
        asyncio.run(verify_seed())
    else:
        try:
            counts = asyncio.run(
                seed_all(
                    dry_run=args.dry_run,
                    clear_existing=args.clear_existing,
                )
            )
            if not args.dry_run:
                logger.info(f"\n--- Summary ---")
                logger.info(f"Industries inserted: {counts['industries']}")
                logger.info(f"Regions inserted: {counts['regions']}")

                # Run verification after seeding
                logger.info("\n--- Verifying seed ---")
                asyncio.run(verify_seed())
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
