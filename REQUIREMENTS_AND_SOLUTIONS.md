# Requirements Breakdown and Proposed Solutions

## Executive Summary

This document breaks down the spoken requirements into structured components and proposes technical solutions for transforming the current MongoDB RAG Agent from a simple chat interface into a comprehensive question-answering system for government consultation responses.

---

## 1. Enhanced Document Metadata Extraction

### 1.1 Requirement
Extract **success/unsuccess status** from documents. Documents contain paragraphs ending with "successful" or "unsuccessful" as the last word, indicating the outcome of the interpretation.

### 1.2 Current State
- Documents are ingested with metadata extracted from headers (ID, date, author, keywords, etc.)
- No extraction of success/unsuccess status
- Metadata extractor (`src/ingestion/metadata_extractor.py`) handles structured header fields

### 1.3 Proposed Solution

**Approach**: Extend `metadata_extractor.py` to scan document content for success indicators.

**Implementation**:
1. **Pattern Detection**: Scan paragraphs for patterns like:
   - Paragraph ending with "successful" / "unsuccessful" (case-insensitive)
   - Context-aware detection (e.g., "interpretation was successful")
   - Multiple indicators per document (track all occurrences)

2. **Metadata Field Addition**:
   ```python
   metadata['outcome_status'] = 'successful' | 'unsuccessful' | 'unknown'
   metadata['outcome_paragraphs'] = [
       {
           'text': '...',
           'status': 'successful',
           'paragraph_index': 5
       }
   ]
   ```

3. **Docling Integration**: Use Docling's paragraph detection to identify paragraph boundaries, then check last words.

**Files to Modify**:
- `src/ingestion/metadata_extractor.py` - Add `extract_outcome_status()` function
- `src/ingestion/ingest.py` - Call new extractor in `_extract_document_metadata()`

**Database Impact**:
- Add `metadata.outcome_status` field to documents collection
- Add `metadata.outcome_paragraphs` array for detailed tracking

---

## 2. Question Processing Architecture

### 2.1 Requirement
When users input questions, the system must:
1. **Extract all questions** from the input (may contain multiple questions)
2. **Process each question individually** (query per question)
3. **Combine answers** into a unified response
4. **Provide document links** for each answer

### 2.2 Current State
- Single question-answer chat interface
- Agent processes one query at a time
- Uses `decompose_question` tool for complex questions, but doesn't handle multiple distinct questions

### 2.3 Proposed Solution

**Approach**: Add question extraction and parallel processing layer.

**Implementation**:

1. **Question Extraction Tool** (`src/tools.py`):
   ```python
   @rag_agent.tool
   async def extract_questions(
       ctx: RunContext,
       user_input: str
   ) -> List[str]:
       """
       Extract individual questions from user input.
       Handles numbered lists, bullet points, multiple sentences.
       """
   ```

2. **Multi-Question Processing** (`src/agent.py`):
   - New agent tool: `process_question_batch(questions: List[str])`
   - For each question:
     - Run RAG search
     - Generate answer with citations
     - Store question-answer pair
   - Combine results into structured response

3. **Response Format**:
   ```json
   {
       "questions": [
           {
               "question": "...",
               "answer": "...",
               "citations": [...],
               "question_id": "uuid"
           }
       ],
       "combined_summary": "..."
   }
   ```

**Files to Create/Modify**:
- `src/tools.py` - Add `extract_questions()` function
- `src/agent.py` - Add `process_question_batch()` tool
- `src/prompts.py` - Update system prompt for multi-question handling

---

## 3. UI Transformation: Chat → Block-Based Editor

### 3.1 Requirement
Replace chat interface with a **block-based UI** where:
- Each question has its own **editable block**
- Each block shows: Question + AI-generated Answer + Document Links
- Users can **edit answers** directly in blocks
- Answers are **persisted** per block

### 3.2 Current State
- Streamlit chat interface (`src/streamlit_app.py`)
- Single conversation thread
- No editing capability
- Citations shown separately

### 3.3 Proposed Solution

**Approach**: Redesign Streamlit UI with block-based layout.

**Implementation**:

1. **New UI Structure** (`src/streamlit_app.py`):
   ```python
   # Session state structure
   st.session_state['qa_blocks'] = [
       {
           'id': 'uuid',
           'question': '...',
           'answer': '...',
           'edited_answer': '...',
           'citations': [...],
           'is_edited': False
       }
   ]
   ```

2. **Block Component**:
   - Question display (read-only or editable)
   - Answer textarea (editable)
   - Citation links below answer
   - Save/Edit buttons
   - Delete block button

3. **Layout**:
   - Input area at top: "Enter questions (one per line or numbered)"
   - Process button: "Generate Answers"
   - Scrollable block list below
   - Export button at bottom

**Files to Modify**:
- `src/streamlit_app.py` - Complete UI redesign
- Create `src/ui_components.py` - Reusable block components

**UI Framework Considerations**:
- Streamlit limitations: Consider if Streamlit can handle complex editing
- Alternative: React-based frontend with FastAPI backend
- Recommendation: Start with Streamlit, migrate if needed

---

## 4. Question-Answer Database Storage

### 4.1 Requirement
Store all question-answer pairs in MongoDB with:
- Question text
- Answer text (original + edited versions)
- Session ID (grouping)
- Session name (user-provided, e.g., company name)
- Document citations
- Timestamps

### 4.2 Current State
- No Q&A storage
- Only document chunks and documents stored
- No session management

### 4.3 Proposed Solution

**Database Schema**:

**New Collection: `qa_sessions`**
```javascript
{
  "_id": ObjectId("..."),
  "session_name": "Company ABC - Tax Consultation 2025",
  "user_role": "junior" | "senior",  // From toggle
  "created_at": ISODate("..."),
  "updated_at": ISODate("..."),
  "status": "draft" | "exported" | "approved",
  "exported_at": ISODate("..."),
  "metadata": {
    "company_info": "...",  // Extracted company information
    "round_number": 1,  // First round, second round, etc.
    "parent_session_id": ObjectId("...")  // For follow-up rounds
  }
}
```

**New Collection: `qa_pairs`**
```javascript
{
  "_id": ObjectId("..."),
  "session_id": ObjectId("..."),  // FK to qa_sessions
  "question": "...",
  "original_answer": "...",  // AI-generated
  "edited_answer": "...",  // User-edited (nullable)
  "final_answer": "...",  // edited_answer or original_answer
  "citations": [
    {
      "document_id": ObjectId("..."),
      "document_title": "...",
      "citation_number": 1,
      "chunk_id": ObjectId("...")
    }
  ],
  "question_index": 0,  // Order in session
  "created_at": ISODate("..."),
  "updated_at": ISODate("..."),
  "status": "draft" | "finalized"
}
```

**Implementation**:

1. **Storage Service** (`src/services/qa_storage.py`):
   ```python
   class QAStorageService:
       async def create_session(name: str, user_role: str) -> str
       async def save_qa_pair(session_id: str, question: str, answer: str, citations: List) -> str
       async def update_answer(qa_pair_id: str, edited_answer: str)
       async def get_session(session_id: str) -> Dict
       async def get_session_qa_pairs(session_id: str) -> List[Dict]
   ```

2. **Integration Points**:
   - After question processing: Save Q&A pairs
   - On answer edit: Update `qa_pairs.edited_answer`
   - On session name input: Update `qa_sessions.session_name`

**Files to Create**:
- `src/services/qa_storage.py` - MongoDB operations for Q&A
- `src/services/__init__.py`

**Files to Modify**:
- `src/streamlit_app.py` - Integrate storage service
- `src/settings.py` - Add collection names

---

## 5. Session Management and Naming

### 5.1 Requirement
- Each Q&A session needs a **unique ID**
- Users can **name sessions** (e.g., company name)
- Sessions persist across browser sessions
- Sessions can be **retrieved** for future reference

### 5.2 Proposed Solution

**UI Flow**:
1. **Session Creation**:
   - On app load: Check for active session in session state
   - If no session: Prompt for session name
   - Create new session in database
   - Store `session_id` in Streamlit session state

2. **Session Selection**:
   - Sidebar: "Load Existing Session"
   - Dropdown: List all sessions (by name + date)
   - Load button: Restore Q&A blocks from database

3. **Session Persistence**:
   - Auto-save on every Q&A pair creation/edit
   - Manual save button: "Save Session"
   - Session list in sidebar

**Implementation**:
- `src/streamlit_app.py` - Session management UI
- `src/services/qa_storage.py` - CRUD operations for sessions

---

## 6. Success/Failure Tracking System

### 6.1 Requirement
Track whether answers were successful:
- **Success**: Government approved (no follow-up questions)
- **Failure**: Government sent more questions
- **Status indicators**: Checkmark (✓) or Cross (✗)
- **Automatic detection**: If new questions uploaded → previous round failed
- **Manual override**: Button "It didn't work, I have more questions"

### 6.2 Proposed Solution

**Database Schema Extension**:

**Update `qa_sessions`**:
```javascript
{
  // ... existing fields
  "outcome_status": "pending" | "successful" | "unsuccessful",
  "outcome_determined_at": ISODate("..."),
  "outcome_determined_by": "automatic" | "manual",
  "follow_up_rounds": [
    {
      "round_number": 2,
      "session_id": ObjectId("..."),
      "created_at": ISODate("...")
    }
  ]
}
```

**Update `qa_pairs`**:
```javascript
{
  // ... existing fields
  "outcome_status": "pending" | "successful" | "unsuccessful",
  "outcome_round": 1,  // Which round this status applies to
}
```

**Workflow Logic**:

1. **Initial Round**:
   - All Q&A pairs: `outcome_status: "pending"`
   - Session: `outcome_status: "pending"`

2. **Export & Send**:
   - Mark session: `status: "exported"`
   - Store `exported_at` timestamp

3. **Follow-up Detection**:
   - **Automatic**: If new questions uploaded for same company/topic:
     - Find parent session
     - Mark parent session: `outcome_status: "unsuccessful"`
     - Mark all Q&A pairs in parent: `outcome_status: "unsuccessful"`
     - Create new session with `parent_session_id` reference
     - Increment `round_number`

   - **Manual**: User clicks "It didn't work" button:
     - Mark current session: `outcome_status: "unsuccessful"`
     - Enable "Add New Questions" flow

4. **Success Detection**:
   - **Automatic**: After export, if no follow-up within X days (configurable):
     - Mark session: `outcome_status: "successful"`
     - Mark all Q&A pairs: `outcome_status: "successful"`

   - **Manual**: User clicks "Approved" button:
     - Mark session: `outcome_status: "successful"`

**Implementation**:
- `src/services/qa_storage.py` - Add outcome tracking methods
- `src/streamlit_app.py` - Add status indicators and buttons
- `src/services/outcome_tracker.py` - Business logic for automatic detection

**Files to Create**:
- `src/services/outcome_tracker.py`

---

## 7. Historical Q&A Retrieval for Similar Questions

### 7.1 Requirement
When answering new questions:
1. Search **document database** (current RAG)
2. Search **Q&A database** for similar questions
3. If similar question found: Use previous answer as **model/reference**
4. Combine both sources in response

### 7.2 Proposed Solution

**Approach**: Extend RAG search to include Q&A similarity search.

**Implementation**:

1. **Q&A Embedding**:
   - When saving Q&A pair: Generate embedding for `question` field
   - Store in `qa_pairs.question_embedding`
   - Only for `outcome_status: "successful"` pairs (or configurable)

2. **Hybrid Search Tool** (`src/tools.py`):
   ```python
   @rag_agent.tool
   async def search_qa_history(
       ctx: RunContext,
       query: str,
       match_count: int = 3
   ) -> List[Dict]:
       """
       Search historical Q&A pairs for similar questions.
       Returns successful Q&A pairs with similarity scores.
       """
   ```

3. **Enhanced Answer Generation**:
   - Search documents (current RAG)
   - Search Q&A history
   - Combine results in prompt:
     ```
     Similar questions from history:
     Q: [previous question]
     A: [previous answer]
     
     Current question: [new question]
     Documents: [RAG results]
     
     Generate answer using both sources.
     ```

4. **Vector Index for Q&A**:
   - Create MongoDB vector index on `qa_pairs.question_embedding`
   - Similar to chunks collection vector search

**Files to Modify**:
- `src/tools.py` - Add `search_qa_history()` function
- `src/agent.py` - Integrate Q&A search into answer generation
- `src/services/qa_storage.py` - Add embedding generation on save
- `scripts/create_indexes.py` - Add Q&A vector index creation

**Database Impact**:
- Add `question_embedding` field to `qa_pairs` collection
- Create vector index: `qa_vector_index` on `question_embedding`

---

## 8. Company Information Extraction

### 8.1 Requirement
Extract company information from user input:
- Company name, industry, activities
- Use as **context** for answering questions
- Store in session metadata

### 8.2 Proposed Solution

**Approach**: Use LLM to extract structured company information.

**Implementation**:

1. **Company Info Extractor** (`src/services/company_extractor.py`):
   ```python
   async def extract_company_info(user_input: str) -> Dict:
       """
       Extract company information using LLM.
       Returns structured data:
       {
           "company_name": "...",
           "industry": "...",
           "activities": ["..."],
           "context": "..."
       }
       """
   ```

2. **Integration**:
   - On session creation: Extract company info from initial input
   - Store in `qa_sessions.metadata.company_info`
   - Include in RAG context for all questions in session

3. **Prompt Enhancement**:
   - Add company context to system prompt
   - "You are answering questions for [Company Name], which [activities]..."

**Files to Create**:
- `src/services/company_extractor.py`

**Files to Modify**:
- `src/streamlit_app.py` - Extract on session creation
- `src/prompts.py` - Include company context

---

## 9. User Role Toggle (Junior vs Senior)

### 9.1 Requirement
- **Toggle at beginning**: Junior or Senior
- **Junior**: Don't store Q&A pairs (not trusted)
- **Senior**: Store Q&A pairs in database

### 9.2 Proposed Solution

**Implementation**:

1. **UI Toggle** (`src/streamlit_app.py`):
   - On app load: Radio button or selectbox
   - "User Role: [ ] Junior [ ] Senior"
   - Store in session state: `st.session_state['user_role']`

2. **Storage Logic** (`src/services/qa_storage.py`):
   ```python
   async def save_qa_pair(..., user_role: str):
       if user_role == "junior":
           # Don't save to database
           # Only store in session state (temporary)
           return None
       else:
           # Save to MongoDB
           return qa_pair_id
   ```

3. **Session Metadata**:
   - Store `user_role` in `qa_sessions.user_role`
   - Filter Q&A history search: Only show senior-created Q&A pairs

**Files to Modify**:
- `src/streamlit_app.py` - Add role toggle
- `src/services/qa_storage.py` - Conditional storage logic

---

## 10. Export Functionality

### 10.1 Requirement
- Export Q&A pairs for sending to government
- Format: Structured document (PDF/Word/Markdown)
- Include: Questions, Answers, Citations

### 10.2 Proposed Solution

**Implementation**:

1. **Export Service** (`src/services/export_service.py`):
   ```python
   class ExportService:
       async def export_session(
           session_id: str,
           format: "pdf" | "docx" | "markdown"
       ) -> bytes:
           """
           Generate export document with:
           - Session name
           - Company info
           - All Q&A pairs (question + final_answer)
           - Citations/references
           """
   ```

2. **Export Formats**:
   - **Markdown**: Simple, includes citations as links
   - **PDF**: Formatted document (use `reportlab` or `weasyprint`)
   - **Word**: `.docx` (use `python-docx`)

3. **UI Button**:
   - "Export Session" button
   - Format selector
   - Download file

**Files to Create**:
- `src/services/export_service.py`

**Files to Modify**:
- `src/streamlit_app.py` - Add export button

---

## 11. Workflow Loop Management

### 11.1 Requirement
Handle iterative rounds:
1. Answer questions → Export → Send to government
2. If questions back → New round (keep history)
3. Use previous Q&A to avoid mistakes
4. Track which round questions belong to

### 11.2 Proposed Solution

**Workflow State Machine**:

```
[New Session] 
    ↓
[Add Questions] 
    ↓
[Generate Answers] 
    ↓
[Edit Answers] 
    ↓
[Export] 
    ↓
[Sent to Government]
    ↓
    ├─→ [No Response] → [Mark Successful] → [End]
    └─→ [More Questions] → [Create Follow-up Session] → [Back to Add Questions]
```

**Implementation**:

1. **Round Tracking**:
   - `qa_sessions.round_number`: Starts at 1
   - `qa_sessions.parent_session_id`: Links to previous round
   - `qa_sessions.follow_up_rounds`: Array of child sessions

2. **Follow-up Session Creation**:
   ```python
   async def create_follow_up_session(
       parent_session_id: str,
       new_questions: List[str]
   ) -> str:
       # Mark parent as unsuccessful
       # Create new session with round_number + 1
       # Link parent_session_id
   ```

3. **Context Injection**:
   - When answering questions in round 2+:
     - Include previous round's Q&A pairs in context
     - Prompt: "Previous answers that didn't work: [list]"
     - "Avoid repeating these mistakes"

**Files to Modify**:
- `src/services/qa_storage.py` - Add follow-up session logic
- `src/agent.py` - Include previous round context in prompts
- `src/streamlit_app.py` - Show round number, parent session link

---

## Implementation Priority

### Phase 1: Core Q&A System
1. ✅ Question extraction and processing
2. ✅ Q&A database storage (sessions + pairs)
3. ✅ Block-based UI (basic)
4. ✅ Session management

### Phase 2: Enhanced Features
5. ✅ Answer editing in blocks
6. ✅ Document citations per answer
7. ✅ Export functionality
8. ✅ Company information extraction

### Phase 3: Intelligence Layer
9. ✅ Success/failure tracking
10. ✅ Historical Q&A search
11. ✅ Outcome status indicators
12. ✅ Follow-up round management

### Phase 4: Metadata Enhancement
13. ✅ Document success/unsuccess extraction
14. ✅ User role toggle
15. ✅ Automatic outcome detection

---

## Database Schema Summary

### New Collections

**`qa_sessions`**
- Session metadata, naming, status, rounds

**`qa_pairs`**
- Individual Q&A pairs with citations, editing history

### Modified Collections

**`documents`**
- Add `metadata.outcome_status`
- Add `metadata.outcome_paragraphs`

**`chunks`**
- No changes (existing structure sufficient)

### New Indexes

1. **Vector Index**: `qa_pairs.question_embedding` → `qa_vector_index`
2. **Text Index**: `qa_pairs.question` → `qa_text_index`
3. **Compound Index**: `qa_sessions.session_name + created_at`
4. **Index**: `qa_pairs.session_id` (for lookups)

---

## Technical Considerations

### 1. Streamlit Limitations
- **Complex Editing**: Streamlit may struggle with rich text editing
- **State Management**: Session state can be fragile
- **Recommendation**: Consider React frontend + FastAPI backend for production

### 2. MongoDB Performance
- **Vector Search**: Ensure Q&A vector index is optimized
- **Aggregation**: Use `$lookup` for joining sessions → pairs
- **Indexing**: All foreign keys and search fields indexed

### 3. Embedding Generation
- **Cost**: Generating embeddings for all Q&A pairs
- **Caching**: Cache embeddings for unchanged questions
- **Batch Processing**: Generate embeddings in batches

### 4. Scalability
- **Session Limits**: Consider pagination for large sessions
- **Q&A History**: Archive old sessions after X months
- **Vector Search**: Limit Q&A history search to recent N months

---

## Open Questions

1. **Success Detection Timing**: How long to wait before auto-marking as successful? (Default: 30 days?)
2. **Q&A History Scope**: Search all historical Q&A or only successful ones?
3. **Export Format**: What format does government expect? (PDF/Word/Markdown?)
4. **Company Info**: Manual input or automatic extraction only?
5. **Editing Permissions**: Can juniors edit senior-created answers?
6. **Session Sharing**: Can multiple users collaborate on same session?

---

## Next Steps

1. **Review & Approve**: Stakeholder review of requirements breakdown
2. **Architecture Review**: Technical architecture validation
3. **Prototype**: Build minimal viable block-based UI
4. **Database Migration**: Create new collections and indexes
5. **Incremental Development**: Implement phase by phase
6. **Testing**: End-to-end workflow testing
7. **Documentation**: User guide for new UI

---

## Appendix: File Structure

```
src/
├── agent.py                    # Modify: Add Q&A batch processing
├── tools.py                     # Modify: Add Q&A history search
├── prompts.py                   # Modify: Multi-question prompts
├── streamlit_app.py            # Major rewrite: Block-based UI
├── settings.py                 # Modify: Add Q&A collection names
├── services/
│   ├── __init__.py
│   ├── qa_storage.py          # NEW: Q&A CRUD operations
│   ├── company_extractor.py   # NEW: Company info extraction
│   ├── export_service.py      # NEW: Export functionality
│   └── outcome_tracker.py     # NEW: Success/failure tracking
├── ingestion/
│   ├── metadata_extractor.py  # Modify: Add outcome status extraction
│   └── ...
└── ui_components.py            # NEW: Reusable UI blocks

scripts/
└── create_indexes.py           # Modify: Add Q&A vector index
```

---

**Document Version**: 1.0  
**Date**: 2025-01-XX  
**Status**: Proposal - Awaiting Approval

