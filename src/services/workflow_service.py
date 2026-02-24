"""Workflow template service for managing workflow templates in MongoDB."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo import AsyncMongoClient

from src.settings import Settings

logger = logging.getLogger(__name__)


# Default stage definitions for the "Polish Tax Interpretations" workflow
DEFAULT_TEMPLATE_NAME = "Polish Tax Interpretations"
DEFAULT_TEMPLATE_DESCRIPTION = "Standard workflow for IP Box / R&D tax interpretations"
DEFAULT_STAGES: List[Dict[str, Any]] = [
    {
        "id": "prep_docs",
        "label": "Prepare documents",
        "description": "Gather and prepare all required documentation",
        "order": 0,
        "color": "#3B82F6",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [
                {"key": "company_nip", "label": "Company NIP", "field_type": "text", "required": True, "options": None}
            ],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "submit_first_instance", "label": "Next", "condition": None}
        ],
    },
    {
        "id": "submit_first_instance",
        "label": "Submit (1st instance)",
        "description": "Submit application to the tax authority (1st instance)",
        "order": 1,
        "color": "#6366F1",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "await_response", "label": "Next", "condition": None}
        ],
    },
    {
        "id": "await_response",
        "label": "Await response",
        "description": "Waiting for tax authority response",
        "order": 2,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "inquiry_check", "label": "Next", "condition": None}
        ],
    },
    {
        "id": "inquiry_check",
        "label": "Inquiry check",
        "description": "Check whether the authority has issued an inquiry for additional information",
        "order": 3,
        "color": "#8B5CF6",
        "config": {
            "system_prompt_append": "Check whether the tax authority has requested additional information. If yes, prepare answers; if no, assess the outcome.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "prepare_answers", "label": "Inquiry received", "condition": None},
            {"to_stage_id": "first_instance_outcome", "label": "No inquiry", "condition": None},
        ],
    },
    {
        "id": "prepare_answers",
        "label": "Prepare answers",
        "description": "Prepare and submit answers to the authority's inquiry",
        "order": 4,
        "color": "#06B6D4",
        "config": {
            "system_prompt_append": "Focus on answering the authority's inquiry precisely and with supporting legal citations.",
            "search_params": {"match_count": 10, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "await_response", "label": "Submit answers", "condition": None}
        ],
    },
    {
        "id": "first_instance_outcome",
        "label": "1st instance outcome",
        "description": "1st instance decision received — determine next step",
        "order": 5,
        "color": "#8B5CF6",
        "config": {
            "system_prompt_append": "Carefully review the tax authority's decision. Identify whether it is positive (refund/favorable interpretation) or negative (rejection), and summarize the key legal arguments.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "end_refund", "label": "Positive outcome", "condition": None},
            {"to_stage_id": "appeal_second_instance", "label": "Negative — appeal", "condition": None},
        ],
    },
    {
        "id": "appeal_second_instance",
        "label": "Appeal (2nd instance)",
        "description": "Decide whether to file an appeal to the 2nd instance authority",
        "order": 6,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "end_no_appeal", "label": "Don't appeal", "condition": None},
            {"to_stage_id": "second_instance_decision", "label": "File appeal", "condition": None},
        ],
    },
    {
        "id": "second_instance_decision",
        "label": "2nd instance decision",
        "description": "2nd instance authority decision received",
        "order": 7,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": "Analyze the second instance authority's decision. Identify grounds for a WSA complaint if the decision is unfavorable.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "complaint_wsa", "label": "Negative — WSA complaint", "condition": None},
            {"to_stage_id": "return_reconsideration", "label": "Successful — reconsider", "condition": None},
        ],
    },
    {
        "id": "complaint_wsa",
        "label": "Complaint to WSA",
        "description": "File a complaint to the Provincial Administrative Court (WSA)",
        "order": 8,
        "color": "#EF4444",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "end_no_appeal", "label": "Don't complain", "condition": None},
            {"to_stage_id": "wsa_decision", "label": "File WSA complaint", "condition": None},
        ],
    },
    {
        "id": "wsa_decision",
        "label": "WSA decision",
        "description": "WSA ruling received",
        "order": 9,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": "Review the WSA ruling carefully. If unfavorable, identify grounds for NSA complaint.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "complaint_nsa", "label": "Negative — NSA complaint", "condition": None},
            {"to_stage_id": "return_reconsideration", "label": "Successful — reconsider", "condition": None},
        ],
    },
    {
        "id": "complaint_nsa",
        "label": "Complaint to NSA",
        "description": "File a complaint to the Supreme Administrative Court (NSA)",
        "order": 10,
        "color": "#DC2626",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "end_no_appeal", "label": "Don't complain", "condition": None},
            {"to_stage_id": "nsa_decision", "label": "File NSA complaint", "condition": None},
        ],
    },
    {
        "id": "nsa_decision",
        "label": "NSA decision",
        "description": "NSA ruling received — final administrative judicial stage",
        "order": 11,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": "Analyze the NSA ruling. This is the final administrative judicial stage.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "end_no_appeal", "label": "Final refusal", "condition": None},
            {"to_stage_id": "return_reconsideration", "label": "Successful — reconsider", "condition": None},
        ],
    },
    {
        "id": "end_refund",
        "label": "End: refund",
        "description": "Case resolved — refund or favorable interpretation granted",
        "order": 12,
        "color": "#10B981",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [],
    },
    {
        "id": "end_no_appeal",
        "label": "End: no appeal",
        "description": "Case closed — no further appeals",
        "order": 13,
        "color": "#6B7280",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [],
    },
    {
        "id": "return_reconsideration",
        "label": "Return for reconsideration",
        "description": "Authority reconsidering — restarting from submission",
        "order": 14,
        "color": "#8B5CF6",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "submit_first_instance", "label": "Resubmit", "condition": None}
        ],
    },
]

DEFAULT_QA_SESSION_TEMPLATE_NAME = "Standard QA Session"
DEFAULT_QA_SESSION_STAGES: List[Dict[str, Any]] = [
    {
        "id": "open",
        "label": "Open",
        "description": "Session started, questions being asked",
        "order": 0,
        "color": "#3B82F6",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [{"to_stage_id": "in_review", "label": "Submit for Review", "condition": None}],
    },
    {
        "id": "in_review",
        "label": "In Review",
        "description": "Session under senior review",
        "order": 1,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": "This session is under senior review. Provide concise, citation-heavy answers.",
            "search_params": {"match_count": 15, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "approved", "label": "Approve", "condition": None},
            {"to_stage_id": "open", "label": "Return for Revision", "condition": None},
        ],
    },
    {
        "id": "approved",
        "label": "Approved",
        "description": "Session approved",
        "order": 2,
        "color": "#10B981",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [{"to_stage_id": "exported", "label": "Export", "condition": None}],
    },
    {
        "id": "exported",
        "label": "Exported",
        "description": "Session exported",
        "order": 3,
        "color": "#8B5CF6",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [],
    },
]

DEFAULT_QA_PAIR_TEMPLATE_NAME = "Standard QA Pair Review"
DEFAULT_QA_PAIR_STAGES: List[Dict[str, Any]] = [
    {
        "id": "draft",
        "label": "Draft",
        "description": "Answer draft",
        "order": 0,
        "color": "#9CA3AF",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [{"to_stage_id": "needs_review", "label": "Flag for Review", "condition": None}],
    },
    {
        "id": "needs_review",
        "label": "Needs Review",
        "description": "Flagged for review",
        "order": 1,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": "This answer requires careful review. Highlight any legal risks.",
            "search_params": {"match_count": 12, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [
            {"to_stage_id": "approved", "label": "Approve", "condition": None},
            {"to_stage_id": "rejected", "label": "Reject", "condition": None},
        ],
    },
    {
        "id": "approved",
        "label": "Approved",
        "description": "Answer approved",
        "order": 2,
        "color": "#10B981",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [{"to_stage_id": "exemplar", "label": "Promote to Exemplar", "condition": None}],
    },
    {
        "id": "rejected",
        "label": "Rejected",
        "description": "Answer rejected",
        "order": 3,
        "color": "#EF4444",
        "config": {
            "system_prompt_append": "Regenerate this answer. The previous version was rejected.",
            "search_params": {"match_count": 15, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [{"to_stage_id": "draft", "label": "Re-generate", "condition": None}],
    },
    {
        "id": "exemplar",
        "label": "Exemplar",
        "description": "Promoted as exemplar answer",
        "order": 4,
        "color": "#8B5CF6",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [],
    },
]

DEFAULT_AGENTIC_TEMPLATE_NAME = "Standard Agentic Pipeline"
DEFAULT_AGENTIC_STAGES: List[Dict[str, Any]] = [
    {
        "id": "question_analysis",
        "label": "Question Analysis",
        "description": "Analyze and decompose the question",
        "order": 0,
        "color": "#3B82F6",
        "config": {
            "system_prompt_append": "First, carefully read the question. Identify: (1) the main legal topic, (2) any sub-questions, (3) required context.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": True,
        },
        "transitions": [{"to_stage_id": "retrieval", "label": "Proceed to Retrieval", "condition": None}],
    },
    {
        "id": "retrieval",
        "label": "Retrieval",
        "description": "Retrieve relevant documents",
        "order": 1,
        "color": "#06B6D4",
        "config": {
            "system_prompt_append": None,
            "search_params": {"match_count": 10, "rrf_k": 60, "qa_history_match_count": 3},
            "metadata_fields": [],
            "auto_advance": True,
        },
        "transitions": [{"to_stage_id": "synthesis", "label": "Synthesize Results", "condition": None}],
    },
    {
        "id": "synthesis",
        "label": "Synthesis",
        "description": "Synthesize retrieved information",
        "order": 2,
        "color": "#8B5CF6",
        "config": {
            "system_prompt_append": "Using the retrieved documents, compose a precise, citation-backed answer. Structure: (1) direct answer, (2) legal basis, (3) caveats.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": True,
        },
        "transitions": [{"to_stage_id": "refinement", "label": "Refine", "condition": None}],
    },
    {
        "id": "refinement",
        "label": "Refinement",
        "description": "Refine and validate the answer",
        "order": 3,
        "color": "#F59E0B",
        "config": {
            "system_prompt_append": "Review your answer for completeness. If key aspects are missing, note what additional context would help.",
            "search_params": {"match_count": 5, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": True,
        },
        "transitions": [{"to_stage_id": "output", "label": "Finalize", "condition": None}],
    },
    {
        "id": "output",
        "label": "Output",
        "description": "Final formatted output",
        "order": 4,
        "color": "#10B981",
        "config": {
            "system_prompt_append": "Format the final answer clearly. Include all citation numbers.",
            "search_params": {"match_count": None, "rrf_k": None, "qa_history_match_count": None},
            "metadata_fields": [],
            "auto_advance": False,
        },
        "transitions": [],
    },
]


class WorkflowService:
    """Service for managing workflow templates in MongoDB."""

    def __init__(self, settings: Settings):
        """
        Initialize workflow service.

        Args:
            settings: Application settings.
        """
        self.settings = settings
        self.mongo_client: Optional[AsyncMongoClient] = None
        self.db: Optional[Any] = None

    @property
    def collection_name(self) -> str:
        return self.settings.mongodb_collection_workflow_templates

    async def initialize(self) -> None:
        """Initialize MongoDB connection."""
        if not self.mongo_client:
            self.mongo_client = AsyncMongoClient(
                self.settings.mongodb_uri, serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[self.settings.mongodb_database]
            await self.mongo_client.admin.command("ping")
            logger.info("Workflow service initialized")

    async def cleanup(self) -> None:
        """Clean up MongoDB connection."""
        if self.mongo_client:
            await self.mongo_client.close()
            self.mongo_client = None
            self.db = None
            logger.info("Workflow service cleaned up")

    def _doc_to_api(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MongoDB document to API-friendly dict."""
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id"))
        return doc

    async def list_templates(self) -> List[Dict[str, Any]]:
        """
        List all workflow templates.

        Returns:
            List of workflow template summary dicts.
        """
        cursor = self.db[self.collection_name].find().sort("created_at", -1)
        templates: List[Dict[str, Any]] = []
        async for doc in cursor:
            api_doc = self._doc_to_api(doc)
            api_doc["stage_count"] = len(api_doc.get("stages", []))
            templates.append(api_doc)
        return templates

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new workflow template.

        Args:
            data: Workflow template data (name, description, is_default, workflow_type, stages).

        Returns:
            Created workflow template dict.
        """
        now = datetime.utcnow()
        workflow_type = data.get("workflow_type", "project")

        # If setting as default, unset any existing default within the same type scope
        if data.get("is_default"):
            if workflow_type == "project":
                type_filter: Dict[str, Any] = {
                    "is_default": True,
                    "$or": [{"workflow_type": "project"}, {"workflow_type": {"$exists": False}}],
                }
            else:
                type_filter = {"is_default": True, "workflow_type": workflow_type}
            await self.db[self.collection_name].update_many(
                type_filter,
                {"$set": {"is_default": False, "updated_at": now}},
            )

        doc = {
            "name": data["name"],
            "description": data.get("description", ""),
            "is_default": data.get("is_default", False),
            "workflow_type": workflow_type,
            "stages": data.get("stages", []),
            "created_at": now,
            "updated_at": now,
        }

        result = await self.db[self.collection_name].insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(f"Created workflow template: {result.inserted_id} ({data['name']})")
        return self._doc_to_api(doc)

    async def get(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get a workflow template by ID.

        Args:
            workflow_id: Workflow template ID.

        Returns:
            Workflow template dict.

        Raises:
            HTTPException: 404 if not found.
        """
        try:
            oid = ObjectId(workflow_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow template not found: {workflow_id}",
            )

        doc = await self.db[self.collection_name].find_one({"_id": oid})
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow template not found: {workflow_id}",
            )
        return self._doc_to_api(doc)

    async def update(self, workflow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a workflow template (full replacement of mutable fields).

        Args:
            workflow_id: Workflow template ID.
            data: Updated workflow template data.

        Returns:
            Updated workflow template dict.

        Raises:
            HTTPException: 404 if not found.
        """
        try:
            oid = ObjectId(workflow_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow template not found: {workflow_id}",
            )

        existing = await self.db[self.collection_name].find_one({"_id": oid})
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow template not found: {workflow_id}",
            )

        now = datetime.utcnow()
        workflow_type = data.get("workflow_type", existing.get("workflow_type", "project"))

        # If setting as default, unset any existing default within the same type scope
        if data.get("is_default") and not existing.get("is_default"):
            if workflow_type == "project":
                type_filter: Dict[str, Any] = {
                    "is_default": True,
                    "_id": {"$ne": oid},
                    "$or": [{"workflow_type": "project"}, {"workflow_type": {"$exists": False}}],
                }
            else:
                type_filter = {
                    "is_default": True,
                    "_id": {"$ne": oid},
                    "workflow_type": workflow_type,
                }
            await self.db[self.collection_name].update_many(
                type_filter,
                {"$set": {"is_default": False, "updated_at": now}},
            )

        update_fields: Dict[str, Any] = {
            "name": data["name"],
            "description": data.get("description", ""),
            "is_default": data.get("is_default", False),
            "workflow_type": workflow_type,
            "stages": data.get("stages", []),
            "updated_at": now,
        }

        await self.db[self.collection_name].update_one(
            {"_id": oid}, {"$set": update_fields}
        )

        return await self.get(workflow_id)

    async def delete(self, workflow_id: str) -> None:
        """
        Delete a workflow template.

        Args:
            workflow_id: Workflow template ID.

        Raises:
            HTTPException: 404 if not found, 409 if default or referenced by projects.
        """
        try:
            oid = ObjectId(workflow_id)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow template not found: {workflow_id}",
            )

        doc = await self.db[self.collection_name].find_one({"_id": oid})
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow template not found: {workflow_id}",
            )

        if doc.get("is_default"):
            raise HTTPException(
                status_code=409,
                detail="Cannot delete the default workflow template",
            )

        # Check if any project references this workflow template
        project_count = await self.db[
            self.settings.mongodb_collection_projects
        ].count_documents({"workflow_template_id": workflow_id})
        if project_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete: {project_count} project(s) reference this workflow template",
            )

        await self.db[self.collection_name].delete_one({"_id": oid})
        logger.info(f"Deleted workflow template: {workflow_id}")

    async def duplicate(
        self, workflow_id: str, new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Duplicate a workflow template.

        Args:
            workflow_id: Source workflow template ID.
            new_name: Name for the copy; defaults to "Copy of <original>".

        Returns:
            New workflow template dict.
        """
        source = await self.get(workflow_id)

        name = new_name or f"Copy of {source['name']}"
        now = datetime.utcnow()

        doc = {
            "name": name,
            "description": source.get("description", ""),
            "is_default": False,  # duplicates are never default
            "workflow_type": source.get("workflow_type", "project"),
            "stages": source.get("stages", []),
            "created_at": now,
            "updated_at": now,
        }

        result = await self.db[self.collection_name].insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(
            f"Duplicated workflow template {workflow_id} -> {result.inserted_id} ({name})"
        )
        return self._doc_to_api(doc)

    async def seed_default(self) -> Dict[str, Any]:
        """
        Seed the default workflow template if none exists. Idempotent.

        Returns:
            The default workflow template dict.
        """
        existing = await self.db[self.collection_name].find_one({"is_default": True})
        if existing:
            return self._doc_to_api(existing)

        now = datetime.utcnow()
        doc = {
            "name": DEFAULT_TEMPLATE_NAME,
            "description": DEFAULT_TEMPLATE_DESCRIPTION,
            "is_default": True,
            "workflow_type": "project",
            "stages": DEFAULT_STAGES,
            "created_at": now,
            "updated_at": now,
        }

        result = await self.db[self.collection_name].insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(f"Seeded default workflow template: {result.inserted_id}")
        return self._doc_to_api(doc)

    async def list_by_type(self, workflow_type: str) -> List[Dict[str, Any]]:
        """List workflow templates filtered by workflow_type.

        Args:
            workflow_type: The workflow type to filter by.

        Returns:
            List of workflow template dicts for the given type.
        """
        if workflow_type == "project":
            query: Dict[str, Any] = {
                "$or": [{"workflow_type": "project"}, {"workflow_type": {"$exists": False}}]
            }
        else:
            query = {"workflow_type": workflow_type}
        cursor = self.db[self.collection_name].find(query).sort("created_at", -1)
        results: List[Dict[str, Any]] = []
        async for doc in cursor:
            item = self._doc_to_api(doc)
            item["stage_count"] = len(doc.get("stages", []))
            results.append(item)
        return results

    async def seed_default_for_type(self, workflow_type: str) -> Dict[str, Any]:
        """Seed the default workflow template for a specific type. Idempotent.

        Args:
            workflow_type: One of "project", "qa_session", "qa_pair", "agentic".

        Returns:
            The existing or newly created default workflow template dict.

        Raises:
            ValueError: If workflow_type is not a valid type.
        """
        _CONFIG: Dict[str, Any] = {
            "project": (DEFAULT_TEMPLATE_NAME, DEFAULT_TEMPLATE_DESCRIPTION, DEFAULT_STAGES),
            "qa_session": (DEFAULT_QA_SESSION_TEMPLATE_NAME, "Default lifecycle for Q&A sessions", DEFAULT_QA_SESSION_STAGES),
            "qa_pair": (DEFAULT_QA_PAIR_TEMPLATE_NAME, "Default lifecycle for individual Q&A pair answers", DEFAULT_QA_PAIR_STAGES),
            "agentic": (DEFAULT_AGENTIC_TEMPLATE_NAME, "Default multi-step AI agent processing pipeline", DEFAULT_AGENTIC_STAGES),
        }
        if workflow_type not in _CONFIG:
            raise ValueError(f"Unknown workflow_type: {workflow_type}")

        if workflow_type == "project":
            query: Dict[str, Any] = {
                "is_default": True,
                "$or": [{"workflow_type": "project"}, {"workflow_type": {"$exists": False}}],
            }
        else:
            query = {"is_default": True, "workflow_type": workflow_type}

        existing = await self.db[self.collection_name].find_one(query)
        if existing:
            if workflow_type == "project":
                # Check if this is the outdated 4-stage placeholder (lacks real pipeline stages)
                existing_stage_ids = {s.get("id") for s in existing.get("stages", [])}
                expected_core_stages = {"prep_docs", "submit_first_instance", "await_response"}
                if not expected_core_stages.issubset(existing_stage_ids):
                    logger.info(
                        "Replacing outdated project workflow template (id=%s) with full 15-stage pipeline",
                        existing["_id"],
                    )
                    await self.db[self.collection_name].delete_one({"_id": existing["_id"]})
                    # Fall through to create the correct template below
                else:
                    return self._doc_to_api(existing)
            else:
                return self._doc_to_api(existing)

        name, description, stages = _CONFIG[workflow_type]
        now = datetime.utcnow()
        doc: Dict[str, Any] = {
            "name": name,
            "description": description,
            "is_default": True,
            "workflow_type": workflow_type,
            "stages": stages,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.db[self.collection_name].insert_one(doc)
        doc["_id"] = result.inserted_id
        logger.info(f"Seeded default {workflow_type} workflow template: {result.inserted_id}")
        return self._doc_to_api(doc)

    async def get_stage(
        self, workflow_id: str, stage_id: str
    ) -> Dict[str, Any]:
        """
        Get a specific stage from a workflow template.

        Args:
            workflow_id: Workflow template ID.
            stage_id: Stage ID within the template.

        Returns:
            Stage dict.

        Raises:
            HTTPException: 404 if workflow or stage not found.
        """
        template = await self.get(workflow_id)
        for stage in template.get("stages", []):
            if stage["id"] == stage_id:
                return stage
        raise HTTPException(
            status_code=404,
            detail=f"Stage '{stage_id}' not found in workflow '{workflow_id}'",
        )

    async def get_resolved_stage_config(
        self,
        workflow_id: str,
        stage_id: str,
        global_settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve stage config with settings inheritance.

        Inheritance: stage overrides -> global stage_defaults -> global settings.

        Args:
            workflow_id: Workflow template ID.
            stage_id: Stage ID within the template.
            global_settings: Current global settings dict.

        Returns:
            Resolved configuration dict with final prompt and search params.
        """
        stage = await self.get_stage(workflow_id, stage_id)
        stage_config = stage.get("config", {})
        stage_search = stage_config.get("search_params", {})

        stage_defaults = global_settings.get("stage_defaults", {})
        defaults_search = stage_defaults.get("search_params", {})

        # Prompt inheritance (additive, skip None segments)
        segments = [global_settings.get("main_system_prompt", "")]
        defaults_append = stage_defaults.get("system_prompt_append")
        if defaults_append is not None:
            segments.append(defaults_append)
        stage_append = stage_config.get("system_prompt_append")
        if stage_append is not None:
            segments.append(stage_append)
        final_prompt = "\n".join(segments)

        # Search param inheritance (stage -> stage_defaults -> global)
        def _resolve(stage_val: Any, default_val: Any, global_val: Any) -> Any:
            if stage_val is not None:
                return stage_val
            if default_val is not None:
                return default_val
            return global_val

        final_match_count = _resolve(
            stage_search.get("match_count"),
            defaults_search.get("match_count"),
            global_settings.get("default_match_count", 10),
        )
        final_rrf_k = _resolve(
            stage_search.get("rrf_k"),
            defaults_search.get("rrf_k"),
            global_settings.get("rrf_k_constant", 60),
        )
        final_qa_history = _resolve(
            stage_search.get("qa_history_match_count"),
            defaults_search.get("qa_history_match_count"),
            global_settings.get("qa_history_match_count", 3),
        )

        return {
            "final_system_prompt": final_prompt,
            "match_count": final_match_count,
            "rrf_k": final_rrf_k,
            "qa_history_match_count": final_qa_history,
            "metadata_fields": stage_config.get("metadata_fields", []),
            "auto_advance": stage_config.get("auto_advance", False),
        }
