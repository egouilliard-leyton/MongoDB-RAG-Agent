"""
Verification: follow-up session creation must NOT change the parent session outcome.

This script performs a minimal, targeted check that does not require LLM calls.
It:
1) Creates a parent session
2) Optionally sets an explicit parent outcome
3) Creates a follow-up session
4) Verifies the parent session outcome_status is unchanged
5) Verifies follow-up metadata (round_number, parent_session_id) is set

Exit code:
0 = success
1 = failure
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add repo root to path so `import src...` works when run from anywhere
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.settings import load_settings  # noqa: E402
from src.services.qa_storage import QAStorageService  # noqa: E402

logger = logging.getLogger(__name__)


async def main_async() -> int:
    load_dotenv()
    settings = load_settings()

    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()

    parent_session_id = None
    follow_up_session_id = None

    try:
        logger.info("Creating parent session…")
        parent_session_id = await qa_storage.create_session(
            name="Verify follow-up outcome behavior",
            user_role="senior",
            company_info={"company_name": "Test Company"},
        )

        # Set a deterministic outcome so we can verify it does not change.
        await qa_storage.mark_session_outcome(
            session_id=parent_session_id,
            outcome="successful",
            determined_by="user",
        )

        parent_before = await qa_storage.get_session(parent_session_id)
        parent_outcome_before = parent_before.get("outcome_status")

        if parent_outcome_before != "successful":
            logger.error(f"Precondition failed: expected parent outcome 'successful', got {parent_outcome_before!r}")
            return 1

        logger.info("Creating follow-up session…")
        follow_up_session_id = await qa_storage.create_follow_up_session(
            parent_session_id=parent_session_id,
            new_questions=["Does follow-up change the parent outcome?"],
            user_role="senior",
        )

        follow_up = await qa_storage.get_session(follow_up_session_id)
        parent_after = await qa_storage.get_session(parent_session_id)
        parent_outcome_after = parent_after.get("outcome_status")

        # Assertions
        if parent_outcome_after != parent_outcome_before:
            logger.error(
                "FAIL: Parent outcome_status changed after follow-up creation: "
                f"{parent_outcome_before!r} -> {parent_outcome_after!r}"
            )
            return 1

        follow_up_parent_id = (follow_up.get("metadata") or {}).get("parent_session_id")
        follow_up_round = (follow_up.get("metadata") or {}).get("round_number")

        if follow_up_parent_id != parent_session_id:
            logger.error(
                "FAIL: Follow-up metadata.parent_session_id mismatch: "
                f"expected {parent_session_id!r}, got {follow_up_parent_id!r}"
            )
            return 1

        if follow_up_round != 2:
            logger.error(f"FAIL: Follow-up round_number mismatch: expected 2, got {follow_up_round!r}")
            return 1

        logger.info("PASS: Follow-up creation does not change parent outcome_status.")
        return 0

    finally:
        # Best-effort cleanup of created sessions (optional)
        try:
            if follow_up_session_id:
                await qa_storage.db[settings.mongodb_collection_qa_sessions].delete_one(
                    {"_id": __import__("bson").ObjectId(follow_up_session_id)}
                )
            if parent_session_id:
                await qa_storage.db[settings.mongodb_collection_qa_sessions].delete_one(
                    {"_id": __import__("bson").ObjectId(parent_session_id)}
                )
        except Exception:
            # Cleanup failures shouldn't mask the main verification result
            logger.warning("Cleanup skipped/failed (non-fatal).")
        await qa_storage.cleanup()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()


