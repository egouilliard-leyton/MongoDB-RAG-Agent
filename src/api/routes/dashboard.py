"""Dashboard API endpoints for analytics and statistics."""

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Query

from src.services.analytics_service import AnalyticsService
from src.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary() -> Dict[str, Any]:
    """
    Get overall dashboard statistics summary.

    Returns comprehensive statistics including:
    - Project, session, and Q&A pair counts
    - Session success rate metrics
    - Q&A quality metrics (good/bad ratios, exemplar count)
    - Timestamp of data generation

    Returns:
        Dictionary containing all dashboard summary metrics
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        summary = await svc.get_dashboard_summary()
        return summary
    finally:
        await svc.cleanup()


@router.get("/distribution/region")
async def get_distribution_by_region() -> Dict[str, Any]:
    """
    Get project and session distribution by region (voivodeship).

    Returns breakdown of projects and sessions grouped by Polish voivodeship.
    Each key in 'projects' and 'sessions' is a region name mapping to a count.

    Returns:
        Dictionary with 'projects' and 'sessions' dicts keyed by region name
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        project_distribution = await svc.get_distribution_by_region()
        session_distribution = await svc.get_session_distribution_by_region()
        return {
            "projects": project_distribution,
            "sessions": session_distribution
        }
    finally:
        await svc.cleanup()


@router.get("/distribution/industry")
async def get_distribution_by_industry() -> Dict[str, Any]:
    """
    Get project distribution by industry classification.

    Returns breakdown of projects grouped by industry category.
    The 'industries' value is a dict mapping industry code to count.

    Returns:
        Dictionary with 'industries' dict keyed by industry code
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        distribution = await svc.get_distribution_by_industry()
        return {"industries": distribution}
    finally:
        await svc.cleanup()


@router.get("/distribution/tax-office")
async def get_distribution_by_tax_office(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of tax offices to return"
    )
) -> Dict[str, Any]:
    """
    Get project distribution by tax office.

    Returns breakdown of projects grouped by tax office,
    with tax office name and city included.
    Results are sorted by count in descending order.

    Args:
        limit: Maximum number of tax offices to return (default: 20, max: 100)

    Returns:
        Dictionary with tax office distribution data including:
        - tax_office_id: The kodjednostki identifier
        - nazwa_urzedu: Tax office name
        - miasto: City
        - count: Number of projects
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        distribution = await svc.get_distribution_by_tax_office(limit=limit)
        return {"tax_offices": distribution}
    finally:
        await svc.cleanup()


@router.get("/trends")
async def get_trends(
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Number of days to look back"
    ),
    granularity: Literal["day", "week", "month"] = Query(
        default="day",
        description="Time granularity for grouping data"
    )
) -> Dict[str, Any]:
    """
    Get time-based trends for projects, sessions, and Q&A pairs.

    Returns time-series data showing the number of new projects, sessions,
    and Q&A pairs created over the specified time period, grouped by the
    specified granularity.

    Args:
        days: Number of days to look back (default: 30, max: 365)
        granularity: Time grouping - "day", "week", or "month" (default: "day")

    Returns:
        Dictionary with trend data including:
        - period_days: Number of days in the analysis period
        - granularity: Time granularity used
        - start_date: Start date of the analysis period
        - projects: List of {date, count} for projects
        - sessions: List of {date, count} for sessions
        - qa_pairs: List of {date, count} for Q&A pairs
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        trends = await svc.get_trends_over_time(days=days, granularity=granularity)
        return trends
    finally:
        await svc.cleanup()


@router.get("/quality")
async def get_quality_metrics() -> Dict[str, Any]:
    """
    Get Q&A quality metrics including good/bad rating ratios.

    Returns detailed metrics about Q&A pair quality:
    - Total Q&A pairs
    - Rated vs unrated counts
    - Good vs bad rating breakdown
    - Good ratio percentage
    - Exemplar count
    - Outcome status distribution (successful/partial/negative)

    Returns:
        Dictionary with quality metrics and outcome distribution
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        quality_metrics = await svc.get_qa_quality_metrics()
        outcome_distribution = await svc.get_outcome_distribution()
        return {
            "quality_metrics": quality_metrics,
            "outcome_distribution": outcome_distribution
        }
    finally:
        await svc.cleanup()


@router.get("/stage-funnel")
async def get_stage_funnel(
    workflow_id: Optional[str] = Query(
        default=None,
        description="Filter by workflow template ID"
    )
) -> Dict[str, Any]:
    """
    Get stage distribution across active projects as a funnel.

    Returns the number and percentage of projects in each workflow stage,
    enriched with label and color from the default workflow template.

    Args:
        workflow_id: Optional workflow template ID to filter projects

    Returns:
        Dictionary with funnel items and total project count
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        return await svc.get_stage_funnel(workflow_id=workflow_id)
    finally:
        await svc.cleanup()


@router.get("/quality-trend")
async def get_quality_trend(
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Number of days to look back"
    ),
    granularity: Literal["day", "week", "month"] = Query(
        default="day",
        description="Time bucket granularity"
    )
) -> Dict[str, Any]:
    """
    Get answer quality trend over time.

    Returns good/bad rating counts and ratios aggregated by time bucket
    over the specified period.

    Args:
        days: Number of days to look back (default: 30, max: 365)
        granularity: Time bucket size - "day", "week", or "month"

    Returns:
        Dictionary with trend data points, period, and granularity
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        return await svc.get_quality_trend(days=days, granularity=granularity)
    finally:
        await svc.cleanup()


@router.get("/kb-health")
async def get_kb_health() -> Dict[str, Any]:
    """
    Get knowledge base health metrics.

    Returns document and chunk counts, embedding coverage, last ingestion
    timestamp, and stale document count.

    Returns:
        Dictionary with KB health metrics
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        return await svc.get_kb_health()
    finally:
        await svc.cleanup()


@router.get("/system-metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """
    Get system performance metrics.

    Returns query counts and placeholder metrics for response times
    and error rates.

    Returns:
        Dictionary with system performance metrics
    """
    settings = load_settings()
    svc = AnalyticsService(settings)
    await svc.initialize()
    try:
        return await svc.get_system_metrics()
    finally:
        await svc.cleanup()
