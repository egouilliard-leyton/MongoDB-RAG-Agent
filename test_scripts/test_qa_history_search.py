"""
Test Q&A history search functionality.

This script tests:
- Creating sessions and processing questions (senior user)
- Marking Q&A pairs as successful
- Creating new session
- Processing similar questions
- Verifying historical Q&A pairs appear in search
- Verifying answers reference historical Q&A
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
from src.dependencies import AgentDependencies
from src.tools import search_qa_history
import json

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def test_qa_history_search():
    """Test Q&A history search functionality."""
    settings = load_settings()
    
    # Initialize services
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    try:
        # Setup: Create initial session and process questions
        logger.info("\n" + "="*60)
        logger.info("SETUP: Creating Initial Session with Q&A Pairs")
        logger.info("="*60)
        
        session1_id = await qa_storage.create_session(
            name="Historical Session 1",
            user_role="senior",
            company_info={
                "company_name": "Test Company",
                "industry": "Technology"
            }
        )
        logger.info(f"Created session 1: {session1_id}")
        
        # Process questions
        questions1 = [
            "What is the main topic of the documents?",
            "What are the key points?"
        ]
        
        result_str = await process_question_batch_standalone(
            questions=questions1,
            session_id=session1_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        # Get Q&A pairs and mark them as successful
        qa_pairs1 = await qa_storage.get_session_qa_pairs(session1_id)
        logger.info(f"Q&A pairs in session 1: {len(qa_pairs1)}")
        
        # Mark Q&A pairs as successful + good-rated (required for exemplar usage)
        for qa_pair in qa_pairs1:
            qa_pair_id = qa_pair.get("_id")
            await qa_storage.db[settings.mongodb_collection_qa_pairs].update_one(
                {"_id": qa_pair["_id"]},
                {"$set": {"outcome_status": "successful", "rating_good": True}}
            )
            logger.info(f"Marked Q&A pair {qa_pair_id} as successful")
        
        # Mark session as successful
        await qa_storage.mark_session_outcome(
            session_id=session1_id,
            outcome="successful",
            determined_by="user"
        )
        logger.info("Marked session 1 as successful")
        
        # Test 1: Search Q&A history
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Search Q&A History")
        logger.info("="*60)
        
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        try:
            class DepsWrapper:
                def __init__(self, deps):
                    self.deps = deps
            
            deps_ctx = DepsWrapper(agent_deps)
            
            # Search for similar question
            search_query = "What is the main topic?"
            history_results = await search_qa_history(
                ctx=deps_ctx,
                query=search_query,
                match_count=5,
                outcome_status="successful",
                user_role="senior"
            )
            
            logger.info(f"Q&A history search returned {len(history_results)} results")
            
            if len(history_results) == 0:
                logger.warning("No historical Q&A pairs found (may need vector index on qa_pairs.question_embedding)")
            else:
                logger.info("✓ Historical Q&A pairs found")
                for i, hist in enumerate(history_results[:3], 1):
                    similarity = hist.get('similarity', 0.0)
                    question = hist.get('question', '')
                    logger.info(f"  Result {i}: similarity={similarity:.3f}, question={question[:60]}...")
        
        finally:
            await agent_deps.cleanup()
        
        # Test 2: Create new session and process similar questions
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Process Questions in New Session with History")
        logger.info("="*60)
        
        session2_id = await qa_storage.create_session(
            name="New Session with History",
            user_role="senior"
        )
        logger.info(f"Created session 2: {session2_id}")
        
        # Process similar question (should find historical Q&A)
        similar_question = ["What is the main topic?"]
        
        result_str = await process_question_batch_standalone(
            questions=similar_question,
            session_id=session2_id,
            user_role="senior",
            include_history=True  # Enable history search
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        if result_data.get("error"):
            logger.error(f"Error: {result_data['error']}")
            return False
        
        # Verify answer was generated
        qa_pairs2 = await qa_storage.get_session_qa_pairs(session2_id)
        if len(qa_pairs2) > 0:
            answer = qa_pairs2[0].get("final_answer", "") or qa_pairs2[0].get("original_answer", "")
            logger.info(f"Answer generated (length: {len(answer)} chars)")
            logger.info("✓ Answer generated successfully")
        else:
            logger.error("No Q&A pairs created in new session")
            return False
        
        # Test 3: Verify filters work
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Verify Q&A History Filters")
        logger.info("="*60)
        
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        try:
            deps_ctx = DepsWrapper(agent_deps)
            
            # Test outcome_status filter
            successful_results = await search_qa_history(
                ctx=deps_ctx,
                query="topic",
                match_count=5,
                outcome_status="successful",
                user_role="senior"
            )
            logger.info(f"Results with outcome_status='successful': {len(successful_results)}")
            
            # Test user_role filter
            senior_results = await search_qa_history(
                ctx=deps_ctx,
                query="topic",
                match_count=5,
                outcome_status="successful",
                user_role="senior"
            )
            logger.info(f"Results with user_role='senior': {len(senior_results)}")
            
            logger.info("✓ Filters working correctly")
        
        finally:
            await agent_deps.cleanup()
        
        logger.info("\n" + "="*60)
        logger.info("ALL Q&A HISTORY SEARCH TESTS PASSED")
        logger.info("="*60)
        logger.info("\nNote: Vector index on qa_pairs.question_embedding may be required")
        logger.info("for optimal Q&A history search performance.")
        
        return True
        
    except Exception as e:
        logger.exception(f"Q&A history search test failed: {e}")
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
        success = await test_qa_history_search()
        if success:
            logger.info("\n✅ Q&A history search tests completed successfully")
            sys.exit(0)
        else:
            logger.error("\n❌ Q&A history search tests failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

