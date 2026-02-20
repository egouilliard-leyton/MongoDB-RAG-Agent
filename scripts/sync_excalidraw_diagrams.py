#!/usr/bin/env python3
"""
Sync Excalidraw diagrams created via MCP to the web interface backend.

This script takes all the diagram elements we created and syncs them to
http://localhost:3000/api/elements/sync so they appear in the web interface.
"""

import json
import requests
import random
from typing import List, Dict, Any

# Base URL for Excalidraw web interface
BASE_URL = "http://localhost:3000"


def create_element(
    element_type: str,
    x: float,
    y: float,
    width: float = None,
    height: float = None,
    text: str = None,
    fontSize: int = 16,
    backgroundColor: str = "transparent",
    strokeColor: str = "#000000",
    **kwargs
) -> Dict[str, Any]:
    """Create a properly formatted Excalidraw element."""
    element = {
        "type": element_type,
        "x": x,
        "y": y,
        "strokeColor": strokeColor,
        "backgroundColor": backgroundColor,
        "fillStyle": "hachure",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": random.randint(100000, 999999),
        "versionNonce": random.randint(100000, 999999),
        "isDeleted": False,
        "updated": int(__import__("time").time() * 1000),
        "link": None,
        "locked": False,
    }
    
    if element_type == "rectangle":
        element.update({
            "width": width or 200,
            "height": height or 60,
        })
        if text:
            element["label"] = {"text": text}
            element["fontSize"] = fontSize
    elif element_type == "arrow":
        element.update({
            "points": kwargs.get("points", [[0, 0], [width or 0, height or 50]]),
            "lastCommittedPoint": None,
            "startBinding": None,
            "endBinding": None,
            "startArrowhead": None,
            "endArrowhead": kwargs.get("endArrowhead", "arrow"),
        })
    elif element_type == "text":
        element.update({
            "text": text or "",
            "fontSize": fontSize,
            "fontFamily": 1,
            "textAlign": "left",
            "verticalAlign": "top",
            "baseline": 0,
            "containerId": None,
            "originalText": text or "",
            "lineHeight": 1.25,
        })
    
    # Override with any additional kwargs
    element.update(kwargs)
    return element


def get_document_ingestion_elements() -> List[Dict[str, Any]]:
    """Document Ingestion Flow diagram elements."""
    elements = []
    base_x, base_y = 50, 50
    
    # User Uploads Document
    elements.append(create_element("rectangle", base_x + 50, base_y, 200, 60, "User Uploads\nDocument", 16))
    
    # Extract Content from File
    elements.append(create_element("rectangle", base_x + 50, base_y + 110, 200, 60, "Extract Content\nfrom File", 16))
    elements.append(create_element("arrow", base_x + 150, base_y + 60, 0, 50, endArrowhead="arrow"))
    
    # Extract Metadata boxes
    elements.append(create_element("rectangle", base_x, base_y + 220, 150, 50, "Extract Metadata", 14))
    elements.append(create_element("rectangle", base_x + 200, base_y + 220, 150, 50, "Extract Metadata", 14))
    elements.append(create_element("rectangle", base_x + 400, base_y + 220, 150, 50, "Extract Metadata", 14))
    
    # Metadata details
    elements.append(create_element("rectangle", base_x, base_y + 310, 150, 50, "ID, Signature\nType, Date", 12))
    elements.append(create_element("rectangle", base_x + 200, base_y + 310, 150, 50, "Title, Author\nKeywords", 12))
    elements.append(create_element("rectangle", base_x + 400, base_y + 310, 150, 50, "Outcome Status\nStance", 12))
    
    # Arrows
    elements.append(create_element("arrow", base_x + 75, base_y + 270, 0, 40, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 275, base_y + 270, 0, 40, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 475, base_y + 270, 0, 40, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 150, base_y + 360, 0, 50, endArrowhead="arrow"))
    
    # Break Document into Chunks
    elements.append(create_element("rectangle", base_x + 50, base_y + 410, 200, 60, "Break Document\ninto Chunks", 16))
    elements.append(create_element("arrow", base_x + 150, base_y + 470, 0, 50, endArrowhead="arrow"))
    
    # Generate Embeddings
    elements.append(create_element("rectangle", base_x + 50, base_y + 520, 200, 60, "Generate Embeddings\nfor Each Chunk", 16))
    elements.append(create_element("arrow", base_x + 100, base_y + 580, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 200, base_y + 580, 0, 50, endArrowhead="arrow"))
    
    # Storage collections
    elements.append(create_element("rectangle", base_x, base_y + 630, 200, 60, "Documents Collection\nFull Content + Metadata", 14, backgroundColor="#fff3e0"))
    elements.append(create_element("rectangle", base_x + 250, base_y + 630, 200, 60, "Chunks Collection\nContent + Embeddings", 14, backgroundColor="#fff3e0"))
    elements.append(create_element("arrow", base_x + 100, base_y + 690, 0, 30, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 350, base_y + 690, 0, 30, endArrowhead="arrow"))
    
    # Final result
    elements.append(create_element("rectangle", base_x + 50, base_y + 720, 400, 50, "Document Ready for Search", 18, backgroundColor="#e8f5e9"))
    
    return elements


def get_project_creation_elements() -> List[Dict[str, Any]]:
    """Project and Company Creation Flow diagram elements."""
    elements = []
    base_x, base_y = 50, 900  # Position below first diagram
    
    # User Creates New Project
    elements.append(create_element("rectangle", base_x + 150, base_y, 200, 60, "User Creates\nNew Project", 16))
    elements.append(create_element("arrow", base_x + 250, base_y + 60, 0, 50, endArrowhead="arrow"))
    
    # Enter details
    elements.append(create_element("rectangle", base_x + 100, base_y + 110, 150, 50, "Enter Project Name", 14))
    elements.append(create_element("rectangle", base_x + 300, base_y + 110, 150, 50, "Enter Company Info", 14))
    elements.append(create_element("arrow", base_x + 250, base_y + 160, 0, 50, endArrowhead="arrow"))
    
    # Project Created
    elements.append(create_element("rectangle", base_x + 150, base_y + 210, 200, 60, "Project Created\nwith Initial Stage", 16, backgroundColor="#e3f2fd"))
    elements.append(create_element("arrow", base_x + 250, base_y + 270, 0, 50, endArrowhead="arrow"))
    
    # Upload Documents / Create Sessions
    elements.append(create_element("rectangle", base_x, base_y + 320, 200, 60, "Upload Documents\nto Project", 14))
    elements.append(create_element("rectangle", base_x + 250, base_y + 320, 200, 60, "Create Sessions\nfor Project", 14))
    elements.append(create_element("arrow", base_x + 100, base_y + 380, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 350, base_y + 380, 0, 50, endArrowhead="arrow"))
    
    # Linked items
    elements.append(create_element("rectangle", base_x, base_y + 430, 200, 60, "Documents Linked\nto Project", 14))
    elements.append(create_element("rectangle", base_x + 250, base_y + 430, 200, 60, "Sessions Linked\nto Project", 14))
    elements.append(create_element("arrow", base_x + 100, base_y + 490, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 350, base_y + 490, 0, 50, endArrowhead="arrow"))
    
    # Final result
    elements.append(create_element("rectangle", base_x + 50, base_y + 540, 400, 60, "Project Contains:\nDocuments + Sessions + Company Info", 16, backgroundColor="#e8f5e9"))
    
    # Project stages sidebar
    elements.append(create_element("rectangle", base_x + 500, base_y + 110, 150, 200, "Project Stages:\n1. Prep Docs\n2. Review Docs\n3. Prep Questions\n4. Process Questions\n5. Review Answers\n6. Finalize", 12))
    
    return elements


def get_session_lifecycle_elements() -> List[Dict[str, Any]]:
    """Session Lifecycle diagram elements."""
    elements = []
    base_x, base_y = 50, 1600  # Position further down
    
    # User Creates New Session
    elements.append(create_element("rectangle", base_x + 150, base_y, 200, 60, "User Creates\nNew Session", 16))
    elements.append(create_element("arrow", base_x + 250, base_y + 60, 0, 50, endArrowhead="arrow"))
    
    # Enter details
    elements.append(create_element("rectangle", base_x + 50, base_y + 110, 150, 50, "Enter Session Name", 14))
    elements.append(create_element("rectangle", base_x + 250, base_y + 110, 150, 50, "Select User Role", 14))
    elements.append(create_element("rectangle", base_x + 450, base_y + 110, 150, 50, "Add Company Info", 14))
    elements.append(create_element("arrow", base_x + 250, base_y + 160, 0, 50, endArrowhead="arrow"))
    
    # Session Created
    elements.append(create_element("rectangle", base_x + 150, base_y + 210, 200, 60, "Session Created\nLinked to Project", 16, backgroundColor="#f3e5f5"))
    elements.append(create_element("arrow", base_x + 250, base_y + 270, 0, 50, endArrowhead="arrow"))
    
    # User roles
    elements.append(create_element("rectangle", base_x + 100, base_y + 320, 150, 50, "Junior User\nAnswers Not Saved", 12))
    elements.append(create_element("rectangle", base_x + 300, base_y + 320, 150, 50, "Senior User\nAnswers Saved", 12))
    elements.append(create_element("arrow", base_x + 175, base_y + 370, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 375, base_y + 370, 0, 50, endArrowhead="arrow"))
    
    # Q&A flows
    elements.append(create_element("rectangle", base_x, base_y + 420, 250, 60, "Ask Questions\nGet Answers\n(Not Saved)", 14))
    elements.append(create_element("rectangle", base_x + 300, base_y + 420, 250, 60, "Ask Questions\nGet Answers\nEdit & Review", 14))
    elements.append(create_element("arrow", base_x + 425, base_y + 480, 0, 50, endArrowhead="arrow"))
    
    # Q&A Pairs Saved
    elements.append(create_element("rectangle", base_x + 300, base_y + 530, 250, 60, "Q&A Pairs Saved\nwith Citations", 14))
    elements.append(create_element("arrow", base_x + 425, base_y + 590, 0, 50, endArrowhead="arrow"))
    
    # Final result
    elements.append(create_element("rectangle", base_x + 150, base_y + 640, 400, 60, "Session Complete\nCan Create Follow-Up Session", 16, backgroundColor="#e8f5e9"))
    
    # Follow-up session info
    elements.append(create_element("rectangle", base_x + 600, base_y + 210, 150, 200, "Follow-Up Session:\n- Links to Parent\n- Includes Previous Context\n- Round Number 2+", 12))
    
    return elements


def get_question_processing_elements() -> List[Dict[str, Any]]:
    """Question Processing Flow diagram elements."""
    elements = []
    base_x, base_y = 50, 2400  # Position further down
    
    # User Uploads Questions
    elements.append(create_element("rectangle", base_x + 200, base_y, 200, 60, "User Uploads\nQuestions", 16))
    elements.append(create_element("arrow", base_x + 300, base_y + 60, 0, 50, endArrowhead="arrow"))
    
    # Extract Individual Questions
    elements.append(create_element("rectangle", base_x + 200, base_y + 110, 200, 60, "Extract Individual\nQuestions", 16))
    elements.append(create_element("arrow", base_x + 300, base_y + 170, 0, 50, endArrowhead="arrow"))
    
    # Simple vs Complex
    elements.append(create_element("rectangle", base_x + 150, base_y + 220, 150, 50, "Simple Question", 14))
    elements.append(create_element("rectangle", base_x + 350, base_y + 220, 150, 50, "Complex Question", 14))
    elements.append(create_element("arrow", base_x + 225, base_y + 270, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 425, base_y + 270, 0, 50, endArrowhead="arrow"))
    
    # Search paths
    elements.append(create_element("rectangle", base_x + 100, base_y + 320, 250, 60, "Search Documents\nDirectly", 14))
    elements.append(create_element("rectangle", base_x + 300, base_y + 320, 250, 60, "Decompose into\nSub-Questions", 14))
    elements.append(create_element("arrow", base_x + 225, base_y + 380, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 425, base_y + 380, 0, 50, endArrowhead="arrow"))
    
    # Sub-question search
    elements.append(create_element("rectangle", base_x + 300, base_y + 430, 250, 60, "Search Each\nSub-Question", 14))
    elements.append(create_element("arrow", base_x + 425, base_y + 490, 0, 50, endArrowhead="arrow"))
    
    # Search types
    elements.append(create_element("rectangle", base_x, base_y + 490, 200, 50, "Semantic Search\n(Meaning)", 12))
    elements.append(create_element("rectangle", base_x + 250, base_y + 490, 200, 50, "Text Search\n(Keywords)", 12))
    elements.append(create_element("rectangle", base_x + 500, base_y + 490, 200, 50, "Q&A History\nSearch", 12))
    elements.append(create_element("arrow", base_x + 100, base_y + 540, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 350, base_y + 540, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 600, base_y + 540, 0, 50, endArrowhead="arrow"))
    
    # Merge results
    elements.append(create_element("rectangle", base_x + 150, base_y + 590, 200, 60, "Merge Search\nResults", 14))
    elements.append(create_element("rectangle", base_x + 400, base_y + 590, 200, 60, "Merge Search\nResults", 14))
    elements.append(create_element("rectangle", base_x + 650, base_y + 590, 200, 60, "Previous Q&A\nContext", 14))
    elements.append(create_element("arrow", base_x + 250, base_y + 650, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 500, base_y + 650, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 750, base_y + 650, 0, 50, endArrowhead="arrow"))
    
    # Generate Answer
    elements.append(create_element("rectangle", base_x + 150, base_y + 700, 600, 60, "Generate Answer with Citations\nUsing AI Synthesis", 16))
    elements.append(create_element("arrow", base_x + 300, base_y + 760, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 500, base_y + 760, 0, 50, endArrowhead="arrow"))
    
    # User types
    elements.append(create_element("rectangle", base_x + 150, base_y + 810, 200, 60, "Junior User\nDisplay Only", 14))
    elements.append(create_element("rectangle", base_x + 450, base_y + 810, 300, 60, "Senior User\nSave Q&A Pair\nwith Citations", 14))
    elements.append(create_element("arrow", base_x + 250, base_y + 870, 0, 30, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 600, base_y + 870, 0, 30, endArrowhead="arrow"))
    
    # Final result
    elements.append(create_element("rectangle", base_x + 150, base_y + 900, 600, 50, "Answer Displayed with Citations", 16, backgroundColor="#e8f5e9"))
    
    return elements


def get_system_overview_elements() -> List[Dict[str, Any]]:
    """System Architecture Overview diagram elements."""
    elements = []
    base_x, base_y = 50, 3400  # Position further down
    
    # User Creates Project
    elements.append(create_element("rectangle", base_x, base_y, 150, 80, "User\nCreates\nProject", 14))
    elements.append(create_element("arrow", base_x + 75, base_y + 80, 0, 50, endArrowhead="arrow"))
    
    # Project Created
    elements.append(create_element("rectangle", base_x, base_y + 130, 150, 60, "Project\nCreated", 14, backgroundColor="#e3f2fd"))
    elements.append(create_element("arrow", base_x + 75, base_y + 190, 0, 50, endArrowhead="arrow"))
    
    # Upload Documents
    elements.append(create_element("rectangle", base_x, base_y + 240, 150, 60, "Upload\nDocuments", 14))
    elements.append(create_element("arrow", base_x + 75, base_y + 300, 0, 50, endArrowhead="arrow"))
    
    # Documents Processed
    elements.append(create_element("rectangle", base_x, base_y + 350, 150, 60, "Documents\nProcessed", 14, backgroundColor="#e8f5e9"))
    elements.append(create_element("arrow", base_x + 150, base_y + 380, 100, 0, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 150, base_y + 410, 100, -270, endArrowhead="arrow"))
    
    # Storage collections
    elements.append(create_element("rectangle", base_x + 250, base_y + 150, 200, 80, "Documents Collection\n- Full Content\n- Metadata\n- Project ID", 12, backgroundColor="#fff3e0"))
    elements.append(create_element("rectangle", base_x + 250, base_y + 350, 200, 80, "Chunks Collection\n- Content\n- Embeddings\n- Document ID", 12, backgroundColor="#fff3e0"))
    
    # Create Session
    elements.append(create_element("arrow", base_x + 75, base_y + 410, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("rectangle", base_x, base_y + 460, 150, 60, "Create\nSession", 14))
    elements.append(create_element("arrow", base_x + 75, base_y + 520, 0, 50, endArrowhead="arrow"))
    
    # Session Created
    elements.append(create_element("rectangle", base_x, base_y + 570, 150, 60, "Session\nCreated", 14, backgroundColor="#f3e5f5"))
    elements.append(create_element("arrow", base_x + 150, base_y + 600, 100, 0, endArrowhead="arrow"))
    elements.append(create_element("rectangle", base_x + 250, base_y + 550, 200, 80, "Sessions Collection\n- Session Name\n- User Role\n- Project ID", 12, backgroundColor="#fff3e0"))
    
    # Ask Questions
    elements.append(create_element("arrow", base_x + 75, base_y + 630, 0, 50, endArrowhead="arrow"))
    elements.append(create_element("rectangle", base_x, base_y + 680, 150, 60, "Ask\nQuestions", 14))
    elements.append(create_element("arrow", base_x + 75, base_y + 740, 0, 50, endArrowhead="arrow"))
    
    # Search Documents
    elements.append(create_element("rectangle", base_x, base_y + 790, 150, 60, "Search\nDocuments", 14))
    elements.append(create_element("arrow", base_x + 150, base_y + 820, 100, 0, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 150, base_y + 820, 100, -270, endArrowhead="arrow"))
    elements.append(create_element("arrow", base_x + 75, base_y + 850, 0, 50, endArrowhead="arrow"))
    
    # Generate Answer
    elements.append(create_element("rectangle", base_x, base_y + 900, 150, 60, "Generate\nAnswer", 14))
    elements.append(create_element("arrow", base_x + 75, base_y + 960, 0, 50, endArrowhead="arrow"))
    
    # Answer with Citations
    elements.append(create_element("rectangle", base_x, base_y + 1010, 150, 60, "Answer\nwith Citations", 14, backgroundColor="#e8f5e9"))
    elements.append(create_element("arrow", base_x + 150, base_y + 1040, 100, 0, endArrowhead="arrow"))
    elements.append(create_element("rectangle", base_x + 250, base_y + 950, 200, 80, "Q&A Pairs Collection\n(Senior Users)\n- Question\n- Answer\n- Citations", 12, backgroundColor="#fff3e0"))
    
    # Sidebar info boxes
    elements.append(create_element("rectangle", base_x + 500, base_y + 150, 200, 100, "Project Stages:\n1. Prep Docs\n2. Review Docs\n3. Prep Questions\n4. Process Questions\n5. Review Answers\n6. Finalize", 11))
    elements.append(create_element("rectangle", base_x + 500, base_y + 350, 200, 80, "Metadata Extracted:\n- ID, Signature\n- Title, Author\n- Keywords\n- Outcome Status", 11))
    elements.append(create_element("rectangle", base_x + 500, base_y + 550, 200, 80, "Session Types:\n- Regular Session\n- Follow-Up Session\n(Round 2+)", 11))
    elements.append(create_element("rectangle", base_x + 500, base_y + 790, 200, 100, "Search Types:\n- Semantic Search\n(Meaning)\n- Text Search\n(Keywords)\n- Hybrid Search\n(Combined)", 11))
    elements.append(create_element("rectangle", base_x + 500, base_y + 950, 200, 80, "Answer Features:\n- Citations\n- Editable (Senior)\n- Rateable (Senior)\n- Exportable", 11))
    
    return elements


def sync_elements(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sync elements to the Excalidraw web interface backend."""
    url = f"{BASE_URL}/api/elements/sync"
    
    try:
        response = requests.post(
            url,
            json={"elements": elements},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def main():
    """Main function to sync all diagrams."""
    print("🔄 Syncing Excalidraw diagrams to web interface...")
    print(f"📍 Target: {BASE_URL}/api/elements/sync\n")
    
    all_elements = []
    
    # Collect all diagram elements
    print("📊 Collecting diagram elements...")
    all_elements.extend(get_document_ingestion_elements())
    print(f"  ✓ Document Ingestion Flow: {len(get_document_ingestion_elements())} elements")
    
    all_elements.extend(get_project_creation_elements())
    print(f"  ✓ Project Creation Flow: {len(get_project_creation_elements())} elements")
    
    all_elements.extend(get_session_lifecycle_elements())
    print(f"  ✓ Session Lifecycle: {len(get_session_lifecycle_elements())} elements")
    
    all_elements.extend(get_question_processing_elements())
    print(f"  ✓ Question Processing Flow: {len(get_question_processing_elements())} elements")
    
    all_elements.extend(get_system_overview_elements())
    print(f"  ✓ System Architecture Overview: {len(get_system_overview_elements())} elements")
    
    print(f"\n📦 Total elements to sync: {len(all_elements)}")
    
    # Sync all elements
    print(f"\n🚀 Syncing to {BASE_URL}...")
    result = sync_elements(all_elements)
    
    if result.get("success"):
        print(f"✅ Successfully synced {result.get('count', 0)} elements!")
        print(f"   Message: {result.get('message', 'N/A')}")
        print(f"\n🌐 Open http://localhost:3000 in your browser to view the diagrams")
        print("   (You may need to refresh the page if it's already open)")
    else:
        print(f"❌ Error syncing elements: {result.get('error', 'Unknown error')}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

