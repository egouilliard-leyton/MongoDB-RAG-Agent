#!/usr/bin/env python3
"""Import Polish tax office data from Excel into MongoDB.

This script reads the tax office data from the provided Excel file
and imports all 590 records into the tax_offices MongoDB collection.

Usage:
    python scripts/import_tax_offices.py
    python scripts/import_tax_offices.py --excel-file "path/to/file.xlsx"
    python scripts/import_tax_offices.py --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
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

# Column mapping from Excel to TaxOffice model fields
COLUMN_MAPPING: Dict[str, str] = {
    "WOJEWÓDZTWO": "wojewodztwo",
    "TYP": "typ",
    "NAZWA URZĘDU": "nazwa_urzedu",
    "KOD": "kod_pocztowy",
    "MIASTO": "miasto",
    "ULICA": "ulica",
    "NR BUDYNKU / LOKALU": "nr_budynku",
    "NR TELEFONU   wraz z nr kierunkowym  ": "telefon",
    "ADRES E-MAIL URZĘDU": "email",
    "kodjednostki": "kodjednostki",
    "ADRESY STRON BIP JEDNOSTEK KAS": "adres_bip",
}


def clean_string(value: Any) -> str:
    """
    Clean and normalize string values from Excel.

    Args:
        value: Raw value from Excel (can be any type)

    Returns:
        Cleaned string value
    """
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_building_number(value: Any) -> str:
    """
    Clean building number field which may contain numeric/float values.

    Args:
        value: Raw building number value

    Returns:
        Cleaned building number as string
    """
    if pd.isna(value):
        return ""
    # Handle float values like 24.26 -> "24.26" or "24/26"
    if isinstance(value, float):
        # Check if it's a whole number
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value).strip()


def read_excel_data(excel_path: Path) -> pd.DataFrame:
    """
    Read tax office data from Excel file.

    Args:
        excel_path: Path to the Excel file

    Returns:
        DataFrame with tax office data

    Raises:
        FileNotFoundError: If Excel file doesn't exist
        ValueError: If required sheet is not found
    """
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    logger.info(f"Reading Excel file: {excel_path}")

    # Read the "Tax offices ID" sheet
    try:
        df = pd.read_excel(excel_path, sheet_name="Tax offices ID")
    except ValueError as e:
        raise ValueError(f"Sheet 'Tax offices ID' not found in Excel file: {e}")

    logger.info(f"Read {len(df)} rows from Excel")
    return df


def transform_row(row: pd.Series) -> Dict[str, Any]:
    """
    Transform an Excel row to a TaxOffice document.

    Args:
        row: Pandas Series representing one row

    Returns:
        Dictionary ready for MongoDB insertion
    """
    doc: Dict[str, Any] = {}

    for excel_col, mongo_field in COLUMN_MAPPING.items():
        if excel_col not in row.index:
            logger.warning(f"Column '{excel_col}' not found in data")
            continue

        value = row[excel_col]

        # Special handling for specific fields
        if mongo_field == "kodjednostki":
            doc[mongo_field] = int(value) if not pd.isna(value) else 0
        elif mongo_field == "nr_budynku":
            doc[mongo_field] = clean_building_number(value)
        else:
            doc[mongo_field] = clean_string(value)

    return doc


def validate_document(doc: Dict[str, Any]) -> List[str]:
    """
    Validate a tax office document.

    Args:
        doc: Tax office document

    Returns:
        List of validation errors (empty if valid)
    """
    errors: List[str] = []

    # Required fields
    required = ["kodjednostki", "nazwa_urzedu", "typ", "wojewodztwo"]
    for field in required:
        if field not in doc or not doc[field]:
            errors.append(f"Missing required field: {field}")

    # kodjednostki must be positive integer
    if "kodjednostki" in doc:
        if not isinstance(doc["kodjednostki"], int) or doc["kodjednostki"] <= 0:
            errors.append(f"Invalid kodjednostki: {doc.get('kodjednostki')}")

    return errors


async def import_tax_offices(
    excel_path: Path,
    dry_run: bool = False,
    clear_existing: bool = False,
) -> int:
    """
    Import tax office data from Excel into MongoDB.

    Args:
        excel_path: Path to the Excel file
        dry_run: If True, validate data but don't insert
        clear_existing: If True, clear existing data before import

    Returns:
        Number of records inserted

    Raises:
        ConnectionFailure: If unable to connect to MongoDB
    """
    settings = load_settings()

    # Read Excel data
    df = read_excel_data(excel_path)

    # Transform and validate all rows
    documents: List[Dict[str, Any]] = []
    validation_errors: List[str] = []

    for idx, row in df.iterrows():
        doc = transform_row(row)
        errors = validate_document(doc)

        if errors:
            validation_errors.extend([f"Row {idx}: {e}" for e in errors])
        else:
            documents.append(doc)

    logger.info(f"Transformed {len(documents)} valid documents")

    if validation_errors:
        logger.warning(f"Found {len(validation_errors)} validation errors:")
        for error in validation_errors[:10]:  # Show first 10 errors
            logger.warning(f"  {error}")
        if len(validation_errors) > 10:
            logger.warning(f"  ... and {len(validation_errors) - 10} more")

    if dry_run:
        logger.info("DRY RUN - No data inserted")
        logger.info(f"Would insert {len(documents)} documents")
        # Show sample document
        if documents:
            logger.info(f"Sample document: {documents[0]}")
        return 0

    # Connect to MongoDB and insert
    logger.info(f"Connecting to MongoDB: {settings.mongodb_database}")
    client: AsyncMongoClient[Dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=10000
    )

    try:
        # Verify connection
        await client.admin.command("ping")
        logger.info("MongoDB connection successful")

        db = client[settings.mongodb_database]
        collection = db[settings.mongodb_collection_tax_offices]

        # Clear existing data if requested
        if clear_existing:
            existing_count = await collection.count_documents({})
            if existing_count > 0:
                logger.info(f"Clearing {existing_count} existing documents")
                await collection.delete_many({})

        # Create indexes before insertion
        logger.info("Creating indexes...")
        await collection.create_index("kodjednostki", unique=True)
        await collection.create_index("nazwa_urzedu")
        await collection.create_index("wojewodztwo")
        await collection.create_index("miasto")
        logger.info("Indexes created successfully")

        # Insert documents
        logger.info(f"Inserting {len(documents)} documents...")
        try:
            result = await collection.insert_many(documents, ordered=False)
            inserted_count = len(result.inserted_ids)
            logger.info(f"Successfully inserted {inserted_count} documents")
        except BulkWriteError as e:
            # Some documents may have been inserted before the error
            inserted_count = e.details.get("nInserted", 0)
            write_errors = e.details.get("writeErrors", [])
            logger.warning(f"Bulk write completed with errors: {len(write_errors)} errors")
            logger.warning(f"Successfully inserted: {inserted_count} documents")

            # Log duplicate key errors (likely from re-running import)
            duplicates = [err for err in write_errors if err.get("code") == 11000]
            if duplicates:
                logger.warning(f"Skipped {len(duplicates)} duplicate records")

        # Verify final count
        final_count = await collection.count_documents({})
        logger.info(f"Total documents in collection: {final_count}")

        return inserted_count

    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    finally:
        await client.close()


async def verify_import() -> None:
    """Verify the import by checking document count and sample data."""
    settings = load_settings()

    client: AsyncMongoClient[Dict[str, Any]] = AsyncMongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=10000
    )

    try:
        await client.admin.command("ping")
        db = client[settings.mongodb_database]
        collection = db[settings.mongodb_collection_tax_offices]

        # Count total documents
        total_count = await collection.count_documents({})
        logger.info(f"Total tax offices in database: {total_count}")

        # Count by region
        pipeline = [
            {"$group": {"_id": "$wojewodztwo", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        logger.info("\nTax offices by region:")
        async for result in collection.aggregate(pipeline):
            logger.info(f"  {result['_id']}: {result['count']}")

        # Show sample documents
        logger.info("\nSample tax offices:")
        cursor = collection.find().limit(3)
        async for doc in cursor:
            logger.info(f"  {doc['kodjednostki']}: {doc['nazwa_urzedu']} ({doc['miasto']})")

        # Verify expected count
        if total_count == 590:
            logger.info("\n✓ Verification PASSED: Expected 590 tax offices, found 590")
        else:
            logger.warning(f"\n⚠ Verification WARNING: Expected 590 tax offices, found {total_count}")

    finally:
        await client.close()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import Polish tax office data from Excel into MongoDB"
    )
    parser.add_argument(
        "--excel-file",
        type=Path,
        default=Path("Data structure, Tax office cooperation 1.xlsx"),
        help="Path to Excel file (default: 'Data structure, Tax office cooperation 1.xlsx')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data without inserting into database",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing tax office data before import",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing data without importing",
    )

    args = parser.parse_args()

    if args.verify_only:
        asyncio.run(verify_import())
    else:
        try:
            count = asyncio.run(
                import_tax_offices(
                    excel_path=args.excel_file,
                    dry_run=args.dry_run,
                    clear_existing=args.clear_existing,
                )
            )
            if not args.dry_run:
                # Run verification after import
                logger.info("\n--- Verifying import ---")
                asyncio.run(verify_import())
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
