"""Analytics service for dashboard statistics and aggregations."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, OperationFailure

from src.settings import Settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for computing dashboard analytics and statistics from MongoDB."""

    def __init__(self, settings: Settings):
        """
        Initialize analytics service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.mongo_client: AsyncMongoClient[Dict[str, Any]] | None = None
        self.db: AsyncDatabase[Dict[str, Any]] | None = None

    async def initialize(self) -> None:
        """
        Initialize MongoDB connection.

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
        """
        if not self.mongo_client:
            try:
                self.mongo_client = AsyncMongoClient(
                    self.settings.mongodb_uri,
                    serverSelectionTimeoutMS=5000
                )
                self.db = self.mongo_client[self.settings.mongodb_database]
                await self.mongo_client.admin.command("ping")
                logger.info("Analytics service initialized")
            except ConnectionFailure:
                logger.exception("mongodb_connection_failed")
                raise

    async def cleanup(self) -> None:
        """Clean up MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Analytics service cleaned up")

    async def get_project_count(self) -> int:
        """
        Get total count of projects.

        Returns:
            Total number of projects in the database

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        try:
            count: int = await self.db[
                self.settings.mongodb_collection_projects
            ].count_documents({})
            return count
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_project_count", "code": e.code}
            )
            raise

    async def get_session_count(self) -> int:
        """
        Get total count of Q&A sessions.

        Returns:
            Total number of sessions in the database

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        try:
            count: int = await self.db[
                self.settings.mongodb_collection_qa_sessions
            ].count_documents({})
            return count
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_session_count", "code": e.code}
            )
            raise

    async def get_success_rate(self) -> Dict[str, Any]:
        """
        Calculate success rate for sessions with outcomes.

        Returns:
            Dictionary with success rate metrics:
            - total_with_outcome: Number of sessions with an outcome set
            - successful: Number of successful sessions
            - unsuccessful: Number of unsuccessful sessions
            - success_rate: Percentage of successful sessions (0-100)

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$match": {
                    "outcome_status": {"$in": ["successful", "unsuccessful"]}
                }
            },
            {
                "$group": {
                    "_id": "$outcome_status",
                    "count": {"$sum": 1}
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_qa_sessions
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=10)

            successful = 0
            unsuccessful = 0

            for result in results:
                if result["_id"] == "successful":
                    successful = result["count"]
                elif result["_id"] == "unsuccessful":
                    unsuccessful = result["count"]

            total_with_outcome = successful + unsuccessful
            success_rate = (
                (successful / total_with_outcome * 100)
                if total_with_outcome > 0
                else 0.0
            )

            return {
                "total_with_outcome": total_with_outcome,
                "successful": successful,
                "unsuccessful": unsuccessful,
                "success_rate": round(success_rate, 2)
            }
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_success_rate", "code": e.code}
            )
            raise

    async def get_distribution_by_region(self) -> List[Dict[str, Any]]:
        """
        Get project distribution by region (voivodeship).

        Returns:
            List of dictionaries with region name and count, sorted by count descending

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$match": {
                    "region": {"$ne": None, "$exists": True}
                }
            },
            {
                "$group": {
                    "_id": "$region",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$project": {
                    "_id": 0,
                    "region": "$_id",
                    "count": 1
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_projects
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=20)
            return results
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_distribution_by_region", "code": e.code}
            )
            raise

    async def get_distribution_by_industry(self) -> List[Dict[str, Any]]:
        """
        Get project distribution by industry classification.

        Returns:
            List of dictionaries with industry name and count, sorted by count descending

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$match": {
                    "industry": {"$ne": None, "$exists": True}
                }
            },
            {
                "$group": {
                    "_id": "$industry",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$project": {
                    "_id": 0,
                    "industry": "$_id",
                    "count": 1
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_projects
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=30)
            return results
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_distribution_by_industry", "code": e.code}
            )
            raise

    async def get_distribution_by_tax_office(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get project distribution by tax office.

        Args:
            limit: Maximum number of tax offices to return (default: 20)

        Returns:
            List of dictionaries with tax office ID, name, and count,
            sorted by count descending

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$match": {
                    "tax_office_id": {"$ne": None, "$exists": True}
                }
            },
            {
                "$group": {
                    "_id": "$tax_office_id",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$limit": limit
            },
            # Join with tax_offices collection to get office name
            {
                "$lookup": {
                    "from": self.settings.mongodb_collection_tax_offices,
                    "localField": "_id",
                    "foreignField": "kodjednostki",
                    "as": "tax_office_info"
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "tax_office_id": "$_id",
                    "count": 1,
                    "nazwa_urzedu": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$tax_office_info.nazwa_urzedu", 0]},
                            "Unknown"
                        ]
                    },
                    "miasto": {
                        "$ifNull": [
                            {"$arrayElemAt": ["$tax_office_info.miasto", 0]},
                            "Unknown"
                        ]
                    }
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_projects
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=limit)
            return results
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_distribution_by_tax_office", "code": e.code}
            )
            raise

    async def get_qa_quality_metrics(self) -> Dict[str, Any]:
        """
        Get Q&A quality metrics including good/bad rating ratios.

        Returns:
            Dictionary with quality metrics:
            - total_qa_pairs: Total number of Q&A pairs
            - rated_count: Number of Q&A pairs that have been rated
            - good_count: Number of pairs rated good
            - bad_count: Number of pairs rated bad
            - unrated_count: Number of pairs not yet rated
            - good_ratio: Percentage of good ratings (out of rated pairs)
            - exemplar_count: Number of Q&A pairs marked as exemplars

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "rated_good": [
                        {"$match": {"rating_good": True}},
                        {"$count": "count"}
                    ],
                    "rated_bad": [
                        {"$match": {"rating_good": False}},
                        {"$count": "count"}
                    ],
                    "exemplars": [
                        {"$match": {"is_exemplar": True}},
                        {"$count": "count"}
                    ]
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_qa_pairs
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=1)

            if not results:
                return {
                    "total_qa_pairs": 0,
                    "rated_count": 0,
                    "good_count": 0,
                    "bad_count": 0,
                    "unrated_count": 0,
                    "good_ratio": 0.0,
                    "exemplar_count": 0
                }

            result = results[0]
            total = result["total"][0]["count"] if result["total"] else 0
            good_count = result["rated_good"][0]["count"] if result["rated_good"] else 0
            bad_count = result["rated_bad"][0]["count"] if result["rated_bad"] else 0
            exemplar_count = (
                result["exemplars"][0]["count"] if result["exemplars"] else 0
            )

            rated_count = good_count + bad_count
            unrated_count = total - rated_count
            good_ratio = (good_count / rated_count * 100) if rated_count > 0 else 0.0

            return {
                "total_qa_pairs": total,
                "rated_count": rated_count,
                "good_count": good_count,
                "bad_count": bad_count,
                "unrated_count": unrated_count,
                "good_ratio": round(good_ratio, 2),
                "exemplar_count": exemplar_count
            }
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_qa_quality_metrics", "code": e.code}
            )
            raise

    async def get_trends_over_time(
        self,
        days: int = 30,
        granularity: str = "day"
    ) -> Dict[str, Any]:
        """
        Get trends over time for projects, sessions, and Q&A pairs.

        Args:
            days: Number of days to look back (default: 30)
            granularity: Time granularity - "day", "week", or "month" (default: "day")

        Returns:
            Dictionary with time-series data for projects, sessions, and Q&A pairs

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        start_date = datetime.utcnow() - timedelta(days=days)

        # Define date format based on granularity
        date_formats = {
            "day": "%Y-%m-%d",
            "week": "%Y-W%V",
            "month": "%Y-%m"
        }
        date_format = date_formats.get(granularity, "%Y-%m-%d")

        # Common pipeline stages for date grouping
        def create_trend_pipeline(date_field: str = "created_at") -> List[Dict[str, Any]]:
            return [
                {
                    "$match": {
                        date_field: {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": date_format,
                                "date": f"${date_field}"
                            }
                        },
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$sort": {"_id": 1}
                },
                {
                    "$project": {
                        "_id": 0,
                        "date": "$_id",
                        "count": 1
                    }
                }
            ]

        try:
            # Get trends for projects
            project_cursor = await self.db[
                self.settings.mongodb_collection_projects
            ].aggregate(create_trend_pipeline())
            project_trends: List[Dict[str, Any]] = await project_cursor.to_list(
                length=100
            )

            # Get trends for sessions
            session_cursor = await self.db[
                self.settings.mongodb_collection_qa_sessions
            ].aggregate(create_trend_pipeline())
            session_trends: List[Dict[str, Any]] = await session_cursor.to_list(
                length=100
            )

            # Get trends for Q&A pairs
            qa_pair_cursor = await self.db[
                self.settings.mongodb_collection_qa_pairs
            ].aggregate(create_trend_pipeline())
            qa_pair_trends: List[Dict[str, Any]] = await qa_pair_cursor.to_list(
                length=100
            )

            return {
                "period_days": days,
                "granularity": granularity,
                "start_date": start_date.isoformat(),
                "projects": project_trends,
                "sessions": session_trends,
                "qa_pairs": qa_pair_trends
            }
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_trends_over_time", "code": e.code}
            )
            raise

    async def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard summary combining all metrics.

        Returns:
            Dictionary with complete dashboard data including:
            - counts: Project, session, Q&A pair counts
            - success_rate: Session success rate metrics
            - quality_metrics: Q&A quality metrics
            - distributions: By region, industry, tax office

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        # Collect all metrics
        project_count = await self.get_project_count()
        session_count = await self.get_session_count()
        success_rate = await self.get_success_rate()
        quality_metrics = await self.get_qa_quality_metrics()

        return {
            "counts": {
                "projects": project_count,
                "sessions": session_count,
                "qa_pairs": quality_metrics["total_qa_pairs"]
            },
            "success_rate": success_rate,
            "quality_metrics": quality_metrics,
            "generated_at": datetime.utcnow().isoformat()
        }

    async def get_outcome_distribution(self) -> Dict[str, int]:
        """
        Get distribution of Q&A pair outcome statuses.

        Returns:
            Dictionary with outcome status distribution:
            - successful: Count of successful outcomes
            - partial: Count of partial outcomes
            - negative: Count of negative outcomes
            - unset: Count of Q&A pairs without outcome set

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$group": {
                    "_id": "$outcome_status",
                    "count": {"$sum": 1}
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_qa_pairs
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=10)

            distribution: Dict[str, int] = {
                "successful": 0,
                "partial": 0,
                "negative": 0,
                "unset": 0
            }

            for result in results:
                status = result["_id"]
                if status is None:
                    distribution["unset"] = result["count"]
                elif status in distribution:
                    distribution[status] = result["count"]

            return distribution
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_outcome_distribution", "code": e.code}
            )
            raise

    async def get_session_distribution_by_region(self) -> List[Dict[str, Any]]:
        """
        Get session distribution by region (voivodeship).

        Returns:
            List of dictionaries with region name and session count,
            sorted by count descending

        Raises:
            ConnectionFailure: If unable to connect to MongoDB
            OperationFailure: If MongoDB operation fails
        """
        await self.initialize()
        assert self.db is not None, "Database not initialized"

        pipeline: List[Dict[str, Any]] = [
            {
                "$match": {
                    "region": {"$ne": None, "$exists": True}
                }
            },
            {
                "$group": {
                    "_id": "$region",
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"count": -1}
            },
            {
                "$project": {
                    "_id": 0,
                    "region": "$_id",
                    "count": 1
                }
            }
        ]

        try:
            cursor = await self.db[
                self.settings.mongodb_collection_qa_sessions
            ].aggregate(pipeline)
            results: List[Dict[str, Any]] = await cursor.to_list(length=20)
            return results
        except OperationFailure as e:
            logger.exception(
                "mongodb_operation_failed",
                extra={"operation": "get_session_distribution_by_region", "code": e.code}
            )
            raise
