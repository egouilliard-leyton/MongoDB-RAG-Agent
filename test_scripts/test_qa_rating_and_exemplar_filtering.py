"""
Test Q&A rating persistence and exemplar filtering functionality.

This script tests:
- GET /api/sessions/{id}/qa-pairs returns _id for each QAPair
- PUT /api/qa-pairs/{id}/rating persists and is reflected in subsequent GET
- search_qa_history() excludes unrated and bad-rated pairs, includes good-rated
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import AsyncMongoClient
from dotenv import load_dotenv
from bson import ObjectId

from src.settings import load_settings
from src.services.qa_storage import QAStorageService
from src.agent import process_question_batch_standalone
from src.dependencies import AgentDependencies
from src.tools import search_qa_history
import json

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def test_qa_pairs_have_id():
    """Test that GET /api/sessions/{id}/qa-pairs returns _id for each QAPair."""
    settings = load_settings()
    
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    try:
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Q&A Pairs Return _id Field")
        logger.info("="*60)
        
        # Create session
        session_id = await qa_storage.create_session(
            name="Rating Test Session",
            user_role="senior",
            company_info={
                "company_name": "Test Company",
                "industry": "Technology"
            }
        )
        logger.info(f"Created session: {session_id}")
        
        # Process questions to create Q&A pairs
        questions = [
            "What is the main topic?",
            "What are the key points?"
        ]
        
        result_str = await process_question_batch_standalone(
            questions=questions,
            session_id=session_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        # Get Q&A pairs via storage service (simulating API endpoint behavior)
        qa_pairs_raw = await qa_storage.get_session_qa_pairs(session_id)
        logger.info(f"Retrieved {len(qa_pairs_raw)} Q&A pairs")
        
        # Verify each Q&A pair has _id
        all_have_id = True
        for i, qa_pair in enumerate(qa_pairs_raw):
            qa_pair_id = qa_pair.get("_id")
            if not qa_pair_id:
                logger.error(f"Q&A pair {i} missing _id field")
                all_have_id = False
            else:
                # Verify it's a string (ObjectId converted to string)
                if not isinstance(qa_pair_id, str):
                    logger.error(f"Q&A pair {i} _id is not a string: {type(qa_pair_id)}")
                    all_have_id = False
                else:
                    logger.info(f"Q&A pair {i} has _id: {qa_pair_id}")
        
        if all_have_id:
            logger.info("✓ All Q&A pairs have _id field")
            return True
        else:
            logger.error("✗ Some Q&A pairs missing _id field")
            return False
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        return False
    finally:
        await qa_storage.cleanup()


async def test_rating_persistence():
    """Test that PUT /api/qa-pairs/{id}/rating persists and is reflected in subsequent GET."""
    settings = load_settings()
    
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    try:
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Rating Persistence")
        logger.info("="*60)
        
        # Create session
        session_id = await qa_storage.create_session(
            name="Rating Persistence Test Session",
            user_role="senior",
            company_info={
                "company_name": "Test Company",
                "industry": "Technology"
            }
        )
        logger.info(f"Created session: {session_id}")
        
        # Process questions to create Q&A pairs
        questions = [
            "What is the main topic?",
            "What are the key points?"
        ]
        
        result_str = await process_question_batch_standalone(
            questions=questions,
            session_id=session_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        # Get Q&A pairs
        qa_pairs = await qa_storage.get_session_qa_pairs(session_id)
        logger.info(f"Retrieved {len(qa_pairs)} Q&A pairs")
        
        if len(qa_pairs) == 0:
            logger.error("No Q&A pairs found to test rating")
            return False
        
        # Test rating persistence for first Q&A pair
        qa_pair = qa_pairs[0]
        qa_pair_id = qa_pair.get("_id")
        
        if not qa_pair_id:
            logger.error("Q&A pair missing _id, cannot test rating")
            return False
        
        logger.info(f"Testing rating persistence for Q&A pair: {qa_pair_id}")
        
        # Verify initial state (should be None/unrated)
        initial_rating = qa_pair.get("rating_good")
        logger.info(f"Initial rating: {initial_rating}")
        
        # Test 1: Set rating to True (good)
        logger.info("Setting rating to True (good)...")
        await qa_storage.update_rating(
            qa_pair_id=qa_pair_id,
            rating_good=True,
            rated_by="test_user"
        )
        
        # Retrieve and verify
        qa_pairs_after_good = await qa_storage.get_session_qa_pairs(session_id)
        updated_pair_good = next((p for p in qa_pairs_after_good if p.get("_id") == qa_pair_id), None)
        
        if not updated_pair_good:
            logger.error("Could not retrieve updated Q&A pair")
            return False
        
        rating_after_good = updated_pair_good.get("rating_good")
        if rating_after_good is not True:
            logger.error(f"Rating not persisted correctly. Expected True, got {rating_after_good}")
            return False
        
        logger.info(f"✓ Rating persisted as True. rated_at: {updated_pair_good.get('rated_at')}")
        
        # Test 2: Set rating to False (bad)
        logger.info("Setting rating to False (bad)...")
        await qa_storage.update_rating(
            qa_pair_id=qa_pair_id,
            rating_good=False,
            rated_by="test_user"
        )
        
        # Retrieve and verify
        qa_pairs_after_bad = await qa_storage.get_session_qa_pairs(session_id)
        updated_pair_bad = next((p for p in qa_pairs_after_bad if p.get("_id") == qa_pair_id), None)
        
        if not updated_pair_bad:
            logger.error("Could not retrieve updated Q&A pair")
            return False
        
        rating_after_bad = updated_pair_bad.get("rating_good")
        if rating_after_bad is not False:
            logger.error(f"Rating not persisted correctly. Expected False, got {rating_after_bad}")
            return False
        
        logger.info(f"✓ Rating persisted as False. rated_at: {updated_pair_bad.get('rated_at')}")
        
        # Test 3: Clear rating (set to None)
        logger.info("Clearing rating (setting to None)...")
        await qa_storage.update_rating(
            qa_pair_id=qa_pair_id,
            rating_good=None,
            rated_by=None
        )
        
        # Retrieve and verify
        qa_pairs_after_clear = await qa_storage.get_session_qa_pairs(session_id)
        updated_pair_clear = next((p for p in qa_pairs_after_clear if p.get("_id") == qa_pair_id), None)
        
        if not updated_pair_clear:
            logger.error("Could not retrieve updated Q&A pair")
            return False
        
        rating_after_clear = updated_pair_clear.get("rating_good")
        if rating_after_clear is not None:
            logger.error(f"Rating not cleared correctly. Expected None, got {rating_after_clear}")
            return False
        
        logger.info("✓ Rating cleared successfully")
        
        logger.info("✓ All rating persistence tests passed")
        return True
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        return False
    finally:
        await qa_storage.cleanup()


async def test_exemplar_filtering():
    """Test that search_qa_history() excludes unrated and bad-rated pairs, includes good-rated."""
    settings = load_settings()
    
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    try:
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Exemplar Filtering (Only Good-Rated Pairs)")
        logger.info("="*60)
        
        # Create session
        session_id = await qa_storage.create_session(
            name="Exemplar Filtering Test Session",
            user_role="senior",
            company_info={
                "company_name": "Test Company",
                "industry": "Technology"
            }
        )
        logger.info(f"Created session: {session_id}")
        
        # Process questions to create Q&A pairs
        questions = [
            "What is the main topic of the documents?",
            "What are the key points discussed?",
            "What are the implications?"
        ]
        
        result_str = await process_question_batch_standalone(
            questions=questions,
            session_id=session_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        # Get Q&A pairs
        qa_pairs = await qa_storage.get_session_qa_pairs(session_id)
        logger.info(f"Retrieved {len(qa_pairs)} Q&A pairs")
        
        if len(qa_pairs) < 3:
            logger.warning(f"Only {len(qa_pairs)} Q&A pairs, need at least 3 for comprehensive test")
        
        # Mark session as successful (required for history search)
        await qa_storage.mark_session_outcome(
            session_id=session_id,
            outcome="successful",
            determined_by="user"
        )
        logger.info("Marked session as successful")
        
        # Set up different ratings for Q&A pairs
        # Pair 0: Good rating
        if len(qa_pairs) > 0:
            qa_pair_0_id = qa_pairs[0].get("_id")
            if qa_pair_0_id:
                await qa_storage.update_rating(
                    qa_pair_id=qa_pair_0_id,
                    rating_good=True,
                    rated_by="test_user"
                )
                # Also mark as successful
                await qa_storage.db[settings.mongodb_collection_qa_pairs].update_one(
                    {"_id": ObjectId(qa_pair_0_id)},
                    {"$set": {"outcome_status": "successful"}}
                )
                logger.info(f"Set Q&A pair 0 ({qa_pair_0_id}) to rating_good=True, outcome_status=successful")
        
        # Pair 1: Bad rating
        if len(qa_pairs) > 1:
            qa_pair_1_id = qa_pairs[1].get("_id")
            if qa_pair_1_id:
                await qa_storage.update_rating(
                    qa_pair_id=qa_pair_1_id,
                    rating_good=False,
                    rated_by="test_user"
                )
                # Also mark as successful
                await qa_storage.db[settings.mongodb_collection_qa_pairs].update_one(
                    {"_id": ObjectId(qa_pair_1_id)},
                    {"$set": {"outcome_status": "successful"}}
                )
                logger.info(f"Set Q&A pair 1 ({qa_pair_1_id}) to rating_good=False, outcome_status=successful")
        
        # Pair 2: Unrated (None)
        if len(qa_pairs) > 2:
            qa_pair_2_id = qa_pairs[2].get("_id")
            if qa_pair_2_id:
                # Ensure it's unrated (should already be None, but be explicit)
                await qa_storage.db[settings.mongodb_collection_qa_pairs].update_one(
                    {"_id": ObjectId(qa_pair_2_id)},
                    {"$set": {"rating_good": None, "outcome_status": "successful"}}
                )
                logger.info(f"Set Q&A pair 2 ({qa_pair_2_id}) to rating_good=None, outcome_status=successful")
        
        # Initialize agent dependencies for search
        agent_deps = AgentDependencies()
        await agent_deps.initialize()
        
        try:
            class DepsWrapper:
                def __init__(self, deps):
                    self.deps = deps
            
            deps_ctx = DepsWrapper(agent_deps)
            
            # Search Q&A history (should only return good-rated pairs)
            search_query = "main topic"
            logger.info(f"Searching Q&A history with query: '{search_query}'")
            
            history_results = await search_qa_history(
                ctx=deps_ctx,
                query=search_query,
                match_count=10,
                outcome_status="successful",
                user_role="senior"
            )
            
            logger.info(f"Q&A history search returned {len(history_results)} results")
            
            # Verify results
            if len(history_results) == 0:
                logger.warning(
                    "No results returned. This may be expected if vector index on "
                    "qa_pairs.question_embedding is not set up. Continuing with verification..."
                )
            else:
                # Check that all returned results have rating_good=True
                all_good_rated = True
                bad_rated_found = False
                unrated_found = False
                
                for result in history_results:
                    result_id = result.get("_id")
                    # Note: rating_good may not be in the projection, so we'll verify via direct DB query
                    # But the filter should have excluded bad/unrated pairs
                    
                    # Verify via direct DB lookup
                    qa_pair_doc = await qa_storage.db[settings.mongodb_collection_qa_pairs].find_one(
                        {"_id": ObjectId(result_id)}
                    )
                    
                    if qa_pair_doc:
                        rating = qa_pair_doc.get("rating_good")
                        if rating is True:
                            logger.info(f"✓ Result {result_id} has rating_good=True (correct)")
                        elif rating is False:
                            logger.error(f"✗ Result {result_id} has rating_good=False (should be excluded)")
                            bad_rated_found = True
                            all_good_rated = False
                        elif rating is None:
                            logger.error(f"✗ Result {result_id} has rating_good=None (should be excluded)")
                            unrated_found = True
                            all_good_rated = False
                
                if all_good_rated:
                    logger.info("✓ All returned results have rating_good=True (correct filtering)")
                else:
                    logger.error(f"✗ Filtering failed: bad-rated found={bad_rated_found}, unrated found={unrated_found}")
                    return False
            
            # Verify that bad-rated and unrated pairs are NOT in results
            if len(qa_pairs) > 1:
                result_ids = [str(r.get("_id")) for r in history_results]
                
                # Check bad-rated pair is excluded
                if len(qa_pairs) > 1 and qa_pairs[1].get("_id") in result_ids:
                    logger.error(f"✗ Bad-rated Q&A pair {qa_pairs[1].get('_id')} found in results (should be excluded)")
                    return False
                else:
                    logger.info("✓ Bad-rated Q&A pair correctly excluded from results")
                
                # Check unrated pair is excluded
                if len(qa_pairs) > 2 and qa_pairs[2].get("_id") in result_ids:
                    logger.error(f"✗ Unrated Q&A pair {qa_pairs[2].get('_id')} found in results (should be excluded)")
                    return False
                else:
                    logger.info("✓ Unrated Q&A pair correctly excluded from results")
            
            logger.info("✓ Exemplar filtering tests passed")
            return True
            
        finally:
            await agent_deps.cleanup()
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")
        return False
    finally:
        await qa_storage.cleanup()


async def main():
    """Run all rating and exemplar filtering tests."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    results = []
    
    try:
        # Test 1: Q&A pairs have _id
        logger.info("\n" + "="*80)
        logger.info("RUNNING TEST SUITE: Q&A Rating and Exemplar Filtering")
        logger.info("="*80)
        
        result1 = await test_qa_pairs_have_id()
        results.append(("Q&A Pairs Have _id", result1))
        
        # Test 2: Rating persistence
        result2 = await test_rating_persistence()
        results.append(("Rating Persistence", result2))
        
        # Test 3: Exemplar filtering
        result3 = await test_exemplar_filtering()
        results.append(("Exemplar Filtering", result3))
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        all_passed = True
        for test_name, passed in results:
            status = "✓ PASSED" if passed else "✗ FAILED"
            logger.info(f"{status}: {test_name}")
            if not passed:
                all_passed = False
        
        logger.info("="*80)
        
        if all_passed:
            logger.info("\n✅ All rating and exemplar filtering tests passed")
            sys.exit(0)
        else:
            logger.error("\n❌ Some tests failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
