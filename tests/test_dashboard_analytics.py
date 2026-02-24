"""Unit tests for AnalyticsService (stage funnel, quality trend, KB health, system metrics)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from bson import ObjectId

from src.services.analytics_service import AnalyticsService


@pytest.fixture
def mock_settings():
    """Create a mock Settings object with collection names."""
    settings = MagicMock()
    settings.mongodb_uri = "mongodb://localhost:27017"
    settings.mongodb_database = "test_db"
    settings.mongodb_collection_projects = "projects"
    settings.mongodb_collection_qa_pairs = "qa_pairs"
    settings.mongodb_collection_qa_sessions = "qa_sessions"
    settings.mongodb_collection_documents = "documents"
    settings.mongodb_collection_chunks = "chunks"
    settings.mongodb_collection_workflow_templates = "workflow_templates"
    settings.mongodb_collection_tax_offices = "tax_offices"
    return settings


@pytest.fixture
def service(mock_settings):
    """Create an AnalyticsService with mocked DB layer."""
    svc = AnalyticsService(mock_settings)
    svc.mongo_client = MagicMock()
    svc.db = MagicMock()
    return svc


def _make_aggregate_mock(results):
    """Create a mock that returns results from aggregate().to_list()."""
    cursor = AsyncMock()
    cursor.to_list = AsyncMock(return_value=results)
    return cursor


# ─── get_stage_funnel ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_stage_funnel_groups_by_stage(service):
    """get_stage_funnel should group projects by stage and compute totals."""
    # Mock the workflow template lookup
    workflow_coll = MagicMock()
    workflow_coll.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "stages": [
            {"id": "intake", "label": "Intake", "color": "#3B82F6", "order": 0},
            {"id": "review", "label": "Review", "color": "#F59E0B", "order": 2},
        ],
    })

    # Mock the project aggregation
    agg_results = [
        {"_id": "intake", "count": 5},
        {"_id": "review", "count": 3},
    ]
    projects_coll = MagicMock()
    projects_coll.aggregate = AsyncMock(return_value=_make_aggregate_mock(agg_results))

    def _get_collection(name):
        if name == "workflow_templates":
            return workflow_coll
        return projects_coll

    service.db.__getitem__ = MagicMock(side_effect=_get_collection)

    result = await service.get_stage_funnel()

    assert result["total_projects"] == 8
    assert len(result["funnel"]) == 2
    assert result["funnel"][0]["stage_id"] == "intake"
    assert result["funnel"][0]["count"] == 5
    assert result["funnel"][0]["label"] == "Intake"
    assert result["funnel"][1]["stage_id"] == "review"
    assert result["funnel"][1]["count"] == 3


@pytest.mark.asyncio
async def test_get_stage_funnel_empty(service):
    """get_stage_funnel should return empty funnel when no projects exist."""
    workflow_coll = MagicMock()
    workflow_coll.find_one = AsyncMock(return_value=None)

    projects_coll = MagicMock()
    projects_coll.aggregate = AsyncMock(return_value=_make_aggregate_mock([]))

    def _get_collection(name):
        if name == "workflow_templates":
            return workflow_coll
        return projects_coll

    service.db.__getitem__ = MagicMock(side_effect=_get_collection)

    result = await service.get_stage_funnel()

    assert result["funnel"] == []
    assert result["total_projects"] == 0


# ─── get_quality_trend ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_quality_trend_computes_ratio(service):
    """get_quality_trend should return trend data with computed ratios."""
    agg_results = [
        {
            "date": "2026-02-01",
            "good_count": 8,
            "bad_count": 2,
            "total_rated": 10,
            "good_ratio": 0.8,
        }
    ]

    qa_coll = MagicMock()
    qa_coll.aggregate = AsyncMock(return_value=_make_aggregate_mock(agg_results))
    service.db.__getitem__ = MagicMock(return_value=qa_coll)

    result = await service.get_quality_trend(days=30, granularity="day")

    assert result["period_days"] == 30
    assert result["granularity"] == "day"
    assert len(result["trend"]) == 1
    assert result["trend"][0]["good_count"] == 8
    assert result["trend"][0]["bad_count"] == 2
    assert result["trend"][0]["good_ratio"] == 0.8


@pytest.mark.asyncio
async def test_get_quality_trend_empty_period(service):
    """get_quality_trend should return empty trend for a period with no data."""
    qa_coll = MagicMock()
    qa_coll.aggregate = AsyncMock(return_value=_make_aggregate_mock([]))
    service.db.__getitem__ = MagicMock(return_value=qa_coll)

    result = await service.get_quality_trend(days=30, granularity="day")

    assert result["trend"] == []
    assert result["period_days"] == 30
    assert result["granularity"] == "day"


# ─── get_kb_health ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_kb_health_returns_all_fields(service):
    """get_kb_health should return all required health metrics."""
    docs_coll = MagicMock()
    docs_coll.count_documents = AsyncMock(side_effect=[100, 5])  # total_documents, stale

    chunks_coll = MagicMock()
    chunks_coll.count_documents = AsyncMock(side_effect=[500, 490])  # total_chunks, embedded

    # list_collection_names
    service.db.list_collection_names = AsyncMock(return_value=["documents", "chunks"])

    def _get_collection(name):
        if name == "documents":
            return docs_coll
        if name == "chunks":
            return chunks_coll
        return MagicMock()

    service.db.__getitem__ = MagicMock(side_effect=_get_collection)

    result = await service.get_kb_health()

    assert result["total_documents"] == 100
    assert result["total_chunks"] == 500
    assert result["avg_chunks_per_doc"] == 5.0
    assert result["embedding_coverage"] == 0.98  # 490/500
    assert result["stale_threshold_days"] == 90
    assert "stale_document_count" in result
    assert "last_ingestion" in result


@pytest.mark.asyncio
async def test_get_kb_health_zero_documents(service):
    """get_kb_health should handle zero documents gracefully."""
    docs_coll = MagicMock()
    docs_coll.count_documents = AsyncMock(side_effect=[0, 0])  # total_documents, stale

    chunks_coll = MagicMock()
    chunks_coll.count_documents = AsyncMock(return_value=0)

    service.db.list_collection_names = AsyncMock(return_value=["documents", "chunks"])

    def _get_collection(name):
        if name == "documents":
            return docs_coll
        if name == "chunks":
            return chunks_coll
        return MagicMock()

    service.db.__getitem__ = MagicMock(side_effect=_get_collection)

    result = await service.get_kb_health()

    assert result["total_documents"] == 0
    assert result["total_chunks"] == 0
    assert result["avg_chunks_per_doc"] == 0.0
    assert result["embedding_coverage"] == 1.0  # special case: 0 chunks -> 1.0


# ─── get_system_metrics ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_system_metrics_returns_query_counts(service):
    """get_system_metrics should return 24h and 7d query counts."""
    qa_coll = MagicMock()
    qa_coll.count_documents = AsyncMock(side_effect=[42, 210])
    service.db.__getitem__ = MagicMock(return_value=qa_coll)

    result = await service.get_system_metrics()

    assert result["total_queries_24h"] == 42
    assert result["total_queries_7d"] == 210
    assert "uptime_seconds" in result
    assert result["avg_response_time_ms"] == 0  # placeholder
    assert result["error_rate_24h"] == 0.0  # placeholder


@pytest.mark.asyncio
async def test_get_system_metrics_zero_queries(service):
    """get_system_metrics should work with zero queries."""
    qa_coll = MagicMock()
    qa_coll.count_documents = AsyncMock(return_value=0)
    service.db.__getitem__ = MagicMock(return_value=qa_coll)

    result = await service.get_system_metrics()

    assert result["total_queries_24h"] == 0
    assert result["total_queries_7d"] == 0
