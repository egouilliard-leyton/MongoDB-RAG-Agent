"""
Test follow-up session creation and context injection.

This script tests:
- Follow-up session creation
- Parent session outcome is NOT automatically modified
- Round number incremented
- Parent session ID set correctly
- Previous Q&A context included in follow-up
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import AsyncMongoClient
from dotenv import load_dotenv

from src.settings import load_settings
from src.services.qa_storage import QAStorageService
from src.agent import process_question_batch_standalone
import json

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def test_follow_up_sessions():
    """Test follow-up session functionality."""
    settings = load_settings()
    
    # Initialize services
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    try:
        # Setup: Create initial session with Q&A pairs
        logger.info("\n" + "="*60)
        logger.info("SETUP: Creating Initial Session with Q&A Pairs")
        logger.info("="*60)
        
        parent_session_id = await qa_storage.create_session(
            name="Initial Test Session",
            user_role="senior",
            company_info={
                "company_name": "Test Company",
                "industry": "Technology"
            }
        )
        logger.info(f"Created parent session: {parent_session_id}")
        
        # Process questions to create Q&A pairs
        initial_questions = [
            "What is the main topic of the documents?",
            "What are the key points?"
        ]
        
        result_str = await process_question_batch_standalone(
            questions=initial_questions,
            session_id=parent_session_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        # Verify Q&A pairs exist
        qa_pairs = await qa_storage.get_session_qa_pairs(parent_session_id)
        logger.info(f"Q&A pairs in parent session: {len(qa_pairs)}")
        
        # Get parent session before follow-up
        parent_session_before = await qa_storage.get_session(parent_session_id)
        parent_round_before = parent_session_before.get("metadata", {}).get("round_number", 1)
        logger.info(f"Parent session round number: {parent_round_before}")
        
        # Test 1: Create follow-up session
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Create Follow-up Session")
        logger.info("="*60)
        
        follow_up_questions = [
            "Can you provide more details?",
            "What are the implications?"
        ]
        
        follow_up_session_id = await qa_storage.create_follow_up_session(
            parent_session_id=parent_session_id,
            new_questions=follow_up_questions,
            user_role="senior"
        )
        logger.info(f"Created follow-up session: {follow_up_session_id}")
        
        # Test 2: Verify parent session outcome is not automatically modified
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Verify Parent Session Outcome Not Auto-Modified")
        logger.info("="*60)
        
        parent_session_after = await qa_storage.get_session(parent_session_id)
        outcome_status = parent_session_after.get("outcome_status")
        
        if outcome_status == parent_session_before.get("outcome_status"):
            logger.info("✓ Parent session outcome_status unchanged (expected)")
        else:
            logger.error(
                "Parent session outcome_status was modified unexpectedly: "
                f"{parent_session_before.get('outcome_status')} -> {outcome_status}"
            )
            return False
        
        # Test 3: Verify round number incremented
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Verify Round Number Incremented")
        logger.info("="*60)
        
        follow_up_session = await qa_storage.get_session(follow_up_session_id)
        follow_up_round = follow_up_session.get("metadata", {}).get("round_number", 1)
        
        logger.info(f"Parent round: {parent_round_before}")
        logger.info(f"Follow-up round: {follow_up_round}")
        
        if follow_up_round == parent_round_before + 1:
            logger.info("✓ Round number incremented correctly")
        else:
            logger.error(f"Round number not incremented correctly: {follow_up_round} != {parent_round_before + 1}")
            return False
        
        # Test 4: Verify parent_session_id set correctly
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Verify Parent Session ID Set")
        logger.info("="*60)
        
        stored_parent_id = follow_up_session.get("metadata", {}).get("parent_session_id")
        logger.info(f"Stored parent_session_id: {stored_parent_id}")
        logger.info(f"Expected parent_session_id: {parent_session_id}")
        
        if stored_parent_id == parent_session_id:
            logger.info("✓ Parent session ID set correctly")
        else:
            logger.error(f"Parent session ID mismatch: {stored_parent_id} != {parent_session_id}")
            return False
        
        # Test 5: Verify previous Q&A context included
        logger.info("\n" + "="*60)
        logger.info("TEST 5: Verify Previous Q&A Context Included")
        logger.info("="*60)
        
        previous_summary = follow_up_session.get("metadata", {}).get("previous_qa_summary", "")
        previous_count = follow_up_session.get("metadata", {}).get("previous_qa_pairs_count", 0)
        
        logger.info(f"Previous Q&A pairs count: {previous_count}")
        logger.info(f"Previous summary length: {len(previous_summary)} chars")
        
        if previous_count == len(qa_pairs):
            logger.info("✓ Previous Q&A pairs count matches")
        else:
            logger.error(f"Previous Q&A count mismatch: {previous_count} != {len(qa_pairs)}")
            return False
        
        if previous_summary:
            logger.info("✓ Previous Q&A summary included")
            logger.info(f"Summary preview: {previous_summary[:200]}...")
        else:
            logger.warning("Previous Q&A summary is empty")
        
        # Test 6: Process questions in follow-up session and verify context injection
        logger.info("\n" + "="*60)
        logger.info("TEST 6: Process Questions in Follow-up Session")
        logger.info("="*60)
        
        result_str = await process_question_batch_standalone(
            questions=follow_up_questions[:1],  # Just one question
            session_id=follow_up_session_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions in follow-up")
        
        if result_data.get("error"):
            logger.error(f"Error processing follow-up questions: {result_data['error']}")
            return False
        
        # Verify follow-up Q&A pairs were created
        follow_up_qa_pairs = await qa_storage.get_session_qa_pairs(follow_up_session_id)
        logger.info(f"Follow-up Q&A pairs: {len(follow_up_qa_pairs)}")
        
        if len(follow_up_qa_pairs) > 0:
            logger.info("✓ Follow-up Q&A pairs created successfully")
            # Check if answer references previous context (basic check)
            answer = follow_up_qa_pairs[0].get("final_answer", "") or follow_up_qa_pairs[0].get("original_answer", "")
            logger.info(f"Answer length: {len(answer)} chars")
        else:
            logger.error("No follow-up Q&A pairs created")
            return False
        
        logger.info("\n" + "="*60)
        logger.info("ALL FOLLOW-UP SESSION TESTS PASSED")
        logger.info("="*60)
        return True
        
    except Exception as e:
        logger.exception(f"Follow-up session test failed: {e}")
        return False
    finally:
        await qa_storage.cleanup()


async def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    try:
        success = await test_follow_up_sessions()
        if success:
            logger.info("\n✅ Follow-up session tests completed successfully")
            sys.exit(0)
        else:
            logger.error("\n❌ Follow-up session tests failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

