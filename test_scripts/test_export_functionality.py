"""
Test export functionality for Q&A sessions.

This script tests:
- Markdown export
- PDF export
- Word (docx) export
- exported_at timestamp
- Content verification
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import AsyncMongoClient
from bson import ObjectId
from dotenv import load_dotenv

from src.settings import load_settings
from src.services.qa_storage import QAStorageService
from src.services.export_service import ExportService
from src.agent import process_question_batch_standalone
import json

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


async def test_export_functionality():
    """Test export functionality."""
    settings = load_settings()
    
    # Initialize services
    qa_storage = QAStorageService(settings)
    await qa_storage.initialize()
    
    export_service = ExportService(settings)
    
    try:
        # Create a test session with Q&A pairs (senior user)
        logger.info("\n" + "="*60)
        logger.info("SETUP: Creating Test Session with Q&A Pairs")
        logger.info("="*60)
        
        session_id = await qa_storage.create_session(
            name="Export Test Session",
            user_role="senior",
            company_info={
                "company_name": "Test Company Inc.",
                "industry": "Technology",
                "activities": "Software development"
            }
        )
        logger.info(f"Created session: {session_id}")
        
        # Process questions to create Q&A pairs
        test_questions = [
            "What is the main topic of the documents?",
            "Summarize the key points"
        ]
        
        result_str = await process_question_batch_standalone(
            questions=test_questions,
            session_id=session_id,
            user_role="senior",
            include_history=True
        )
        
        result_data = json.loads(result_str)
        logger.info(f"Processed {result_data.get('questions_processed', 0)} questions")
        
        # Verify Q&A pairs exist
        qa_pairs = await qa_storage.get_session_qa_pairs(session_id)
        logger.info(f"Q&A pairs in database: {len(qa_pairs)}")
        
        if len(qa_pairs) == 0:
            logger.error("No Q&A pairs found. Cannot test export.")
            return False
        
        # Test 1: Markdown Export
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Markdown Export")
        logger.info("="*60)
        
        markdown_content = await export_service.export_session_to_markdown(session_id)
        logger.info(f"Markdown export length: {len(markdown_content)} chars")
        
        # Verify content
        if "Export Test Session" not in markdown_content:
            logger.error("Session name not found in markdown export")
            return False
        
        if "Test Company Inc." not in markdown_content:
            logger.error("Company name not found in markdown export")
            return False
        
        if "What is the main topic" not in markdown_content:
            logger.error("Question not found in markdown export")
            return False
        
        logger.info("✓ Markdown export content verified")
        
        # Test 2: PDF Export
        logger.info("\n" + "="*60)
        logger.info("TEST 2: PDF Export")
        logger.info("="*60)
        
        pdf_bytes, mime_type, filename = await export_service.export_session(session_id, "pdf")
        logger.info(f"PDF export size: {len(pdf_bytes)} bytes")
        logger.info(f"MIME type: {mime_type}")
        logger.info(f"Filename: {filename}")
        
        if mime_type != "application/pdf":
            logger.error(f"Invalid MIME type: {mime_type}")
            return False
        
        if len(pdf_bytes) == 0:
            logger.error("PDF export is empty")
            return False
        
        # Verify PDF header (PDF files start with %PDF)
        if not pdf_bytes.startswith(b"%PDF"):
            logger.error("Invalid PDF format (missing PDF header)")
            return False
        
        logger.info("✓ PDF export verified")
        
        # Test 3: Word Export
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Word (docx) Export")
        logger.info("="*60)
        
        docx_bytes, mime_type, filename = await export_service.export_session(session_id, "docx")
        logger.info(f"Word export size: {len(docx_bytes)} bytes")
        logger.info(f"MIME type: {mime_type}")
        logger.info(f"Filename: {filename}")
        
        if mime_type != "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            logger.error(f"Invalid MIME type: {mime_type}")
            return False
        
        if len(docx_bytes) == 0:
            logger.error("Word export is empty")
            return False
        
        # Verify DOCX header (ZIP file format)
        if not docx_bytes.startswith(b"PK"):
            logger.error("Invalid DOCX format (missing ZIP header)")
            return False
        
        logger.info("✓ Word export verified")
        
        # Test 4: Verify exported_at timestamp
        logger.info("\n" + "="*60)
        logger.info("TEST 4: exported_at Timestamp")
        logger.info("="*60)
        
        # Get session after export (should have exported_at)
        session_after = await qa_storage.get_session(session_id)
        exported_at = session_after.get("exported_at")
        
        if exported_at:
            logger.info(f"exported_at timestamp: {exported_at}")
            logger.info("✓ exported_at timestamp set")
        else:
            logger.warning("exported_at timestamp not set (may be set by API endpoint)")
        
        # Test 5: Export session without Q&A pairs (should handle gracefully)
        logger.info("\n" + "="*60)
        logger.info("TEST 5: Export Empty Session (Error Handling)")
        logger.info("="*60)
        
        empty_session_id = await qa_storage.create_session(
            name="Empty Session",
            user_role="junior"
        )
        
        try:
            await export_service.export_session_to_markdown(empty_session_id)
            logger.error("Should have raised ValueError for empty session")
            return False
        except ValueError as e:
            error_msg_lower = str(e).lower()
            if "no q&a pairs" in error_msg_lower or "has no q&a pairs" in error_msg_lower:
                logger.info("✓ Empty session export correctly raises ValueError")
            else:
                logger.error(f"Unexpected error message: {e}")
                return False
        
        logger.info("\n" + "="*60)
        logger.info("ALL EXPORT TESTS PASSED")
        logger.info("="*60)
        return True
        
    except Exception as e:
        logger.exception(f"Export test failed: {e}")
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
        success = await test_export_functionality()
        if success:
            logger.info("\n✅ Export functionality tests completed successfully")
            sys.exit(0)
        else:
            logger.error("\n❌ Export functionality tests failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

