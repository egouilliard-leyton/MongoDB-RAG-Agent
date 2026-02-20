"""Tax office storage service for managing Polish tax office reference data."""

import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, OperationFailure

from src.settings import Settings

logger = logging.getLogger(__name__)


class TaxOfficeStorageService:
    """Service for managing tax office reference data in MongoDB."""

    def __init__(self, settings: Settings):
        """
        Initialize tax office storage service.

        Args:
            settings: Application settings with MongoDB configuration
        """
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient[Dict[str, Any]]] = None
        self.db: Optional[AsyncDatabase[Dict[str, Any]]] = None

    @property
    def collection_name(self) -> str:
        """Get collection name for tax offices."""
        return self.settings.mongodb_collection_tax_offices

    async def initialize(self) -> None:
        """
        Initialize MongoDB connection and create indexes.

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
        """
        if not self.mongo_client:
            try:
                self.mongo_client = AsyncMongoClient(
                    self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
                )
                self.db = self.mongo_client[self.settings.mongodb_database]
                await self.mongo_client.admin.command("ping")

                # Create indexes for efficient querying
                collection = self.db[self.collection_name]
                await collection.create_index("kodjednostki", unique=True)
                await collection.create_index("nazwa_urzedu")
                await collection.create_index("wojewodztwo")
                await collection.create_index("miasto")

                logger.info("Tax office storage service initialized")
            except ConnectionFailure as e:
                logger.exception("mongodb_connection_failed")
                raise

    async def cleanup(self) -> None:
        """Close MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Tax office storage service cleaned up")

    def _tax_office_to_api(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert MongoDB document to API-friendly format.

        Args:
            doc: MongoDB document

        Returns:
            Document with _id converted to string
        """
        doc = dict(doc)
        doc["_id"] = str(doc["_id"])
        return doc

    async def create_tax_office(
        self,
        kodjednostki: int,
        nazwa_urzedu: str,
        typ: str,
        wojewodztwo: str,
        miasto: str,
        ulica: str,
        nr_budynku: str,
        kod_pocztowy: str,
        telefon: str,
        email: str,
        adres_bip: str,
    ) -> str:
        """
        Create a new tax office record.

        Args:
            kodjednostki: Unique tax office ID
            nazwa_urzedu: Office name
            typ: Type (IAS/US)
            wojewodztwo: Region (voivodeship)
            miasto: City
            ulica: Street
            nr_budynku: Building number
            kod_pocztowy: Postal code
            telefon: Phone number
            email: Email address
            adres_bip: BIP website URL

        Returns:
            Inserted document ID as string

        Raises:
            ValueError: If tax office with kodjednostki already exists
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        tax_office_doc: Dict[str, Any] = {
            "kodjednostki": kodjednostki,
            "nazwa_urzedu": nazwa_urzedu,
            "typ": typ,
            "wojewodztwo": wojewodztwo,
            "miasto": miasto,
            "ulica": ulica,
            "nr_budynku": nr_budynku,
            "kod_pocztowy": kod_pocztowy,
            "telefon": telefon,
            "email": email,
            "adres_bip": adres_bip,
        }

        try:
            result = await self.db[self.collection_name].insert_one(tax_office_doc)
            return str(result.inserted_id)
        except OperationFailure as e:
            if "duplicate key" in str(e).lower():
                raise ValueError(f"Tax office with kodjednostki {kodjednostki} already exists")
            raise

    async def get_tax_office_by_id(self, kodjednostki: int) -> Optional[Dict[str, Any]]:
        """
        Get tax office by kodjednostki ID.

        Args:
            kodjednostki: Tax office ID

        Returns:
            Tax office document or None if not found
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"
        doc = await self.db[self.collection_name].find_one({"kodjednostki": kodjednostki})
        return self._tax_office_to_api(doc) if doc else None

    async def list_tax_offices(
        self, limit: int = 600, skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all tax offices with pagination.

        Args:
            limit: Maximum number of results (default: 600)
            skip: Number of results to skip (default: 0)

        Returns:
            List of tax office documents
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"
        cursor = (
            self.db[self.collection_name]
            .find()
            .sort("nazwa_urzedu", 1)
            .skip(skip)
            .limit(limit)
        )
        tax_offices: List[Dict[str, Any]] = []
        async for office in cursor:
            tax_offices.append(self._tax_office_to_api(office))
        return tax_offices

    async def search_tax_offices(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search tax offices by name, city, or kodjednostki.

        Uses case-insensitive regex matching on nazwa_urzedu and miasto fields.
        Also searches by exact kodjednostki if query is numeric.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 20)

        Returns:
            List of matching tax office documents
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        # Try to parse query as integer for kodjednostki search
        kod_filter: Optional[Dict[str, int]] = None
        try:
            kodjednostki = int(query)
            kod_filter = {"kodjednostki": kodjednostki}
        except ValueError:
            pass

        # Build regex search filter
        search_filter: Dict[str, Any] = {
            "$or": [
                {"nazwa_urzedu": {"$regex": query, "$options": "i"}},
                {"miasto": {"$regex": query, "$options": "i"}},
            ]
        }

        if kod_filter:
            search_filter["$or"].append(kod_filter)

        cursor = (
            self.db[self.collection_name]
            .find(search_filter)
            .sort("nazwa_urzedu", 1)
            .limit(limit)
        )

        tax_offices: List[Dict[str, Any]] = []
        async for office in cursor:
            tax_offices.append(self._tax_office_to_api(office))
        return tax_offices

    async def get_tax_offices_by_region(self, wojewodztwo: str) -> List[Dict[str, Any]]:
        """
        Get all tax offices in a specific region (voivodeship).

        Args:
            wojewodztwo: Region name

        Returns:
            List of tax office documents in the region
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"
        cursor = (
            self.db[self.collection_name]
            .find({"wojewodztwo": wojewodztwo})
            .sort("nazwa_urzedu", 1)
        )

        tax_offices: List[Dict[str, Any]] = []
        async for office in cursor:
            tax_offices.append(self._tax_office_to_api(office))
        return tax_offices

    async def get_tax_offices_grouped_by_region(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all tax offices grouped by region.

        Returns:
            Dictionary mapping region names to lists of tax offices
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"
        pipeline: List[Dict[str, Any]] = [
            {"$sort": {"wojewodztwo": 1, "nazwa_urzedu": 1}},
            {
                "$group": {
                    "_id": "$wojewodztwo",
                    "tax_offices": {"$push": "$$ROOT"},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        result: Dict[str, List[Dict[str, Any]]] = {}
        cursor = await self.db[self.collection_name].aggregate(pipeline)
        async for group in cursor:
            region = group["_id"]
            offices = [self._tax_office_to_api(office) for office in group["tax_offices"]]
            result[region] = offices

        return result

    async def count_tax_offices(self) -> int:
        """
        Get total count of tax offices.

        Returns:
            Total number of tax office documents
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"
        count: int = await self.db[self.collection_name].count_documents({})
        return count
