# How Question Processing Works

This guide explains how questions are processed, how complex questions are broken down, how the system searches for answers, and how answers are generated with citations. Understanding this process helps you get the best results from the system.

> **Visual Diagram**: A comprehensive flow diagram showing the complete question processing flow is available in Excalidraw. The diagram illustrates question upload, decomposition, document search, answer generation, and storage for both Junior and Senior users.

## Introduction

When you ask questions in a session, the system goes through a sophisticated process to find the most relevant information and generate accurate answers. This process involves searching through documents, considering previous Q&A history, and using artificial intelligence to provide comprehensive answers with proper citations.

## Prerequisites

- An active session created in the application
- Documents uploaded and ingested (either project-specific or general)
- Understanding of how to enter questions in the interface

## The Question Processing Flow

### Step 1: Question Upload

When you submit questions:

1. Enter one or more questions in the question input area
2. Questions can be entered as:
   - A single question
   - Multiple questions (one per line)
   - Numbered lists of questions
3. Click "Generate Answers" or "Process Questions"
4. The system receives your questions and begins processing

### Step 2: Question Extraction

The system automatically:

- Separates multiple questions if you entered several
- Cleans up formatting (removes numbers, bullets, etc.)
- Identifies each individual question
- Numbers them in order (question_index: 1, 2, 3...)

**Example**: If you enter:
```
1. What is the tax treatment?
2. How does this apply to our situation?
3. What are the requirements?
```

The system extracts three separate questions and processes each one.

### Step 3: Question Decomposition

For each question, the system analyzes whether it's simple or complex:

#### Simple Questions

Questions that ask about a single topic:
- "What is the tax rate?"
- "When was this document published?"
- "Who is the author?"

These are processed directly without decomposition.

#### Complex Questions

Questions that ask about multiple topics or require comparisons:
- "What are the benefits and drawbacks of this approach?"
- "How does option A compare to option B?"
- "What are the requirements for both scenarios?"

**Decomposition Process**:

1. **Complexity Analysis**: The system analyzes the question to determine if it's complex
2. **Sub-Question Identification**: Complex questions are broken into smaller, focused sub-questions
3. **Reasoning**: The system explains why decomposition is needed
4. **Separate Processing**: Each sub-question is processed independently

**Example Decomposition**:

**Original Question**: "What are the benefits and drawbacks of this tax treatment?"

**Sub-Questions Created**:
1. "What are the benefits of this tax treatment?"
2. "What are the drawbacks of this tax treatment?"

Each sub-question is then searched and answered separately, and the results are combined into a comprehensive answer.

### Step 4: Document Search

For each question (or sub-question), the system searches for relevant information:

#### Search Process

The system performs a **hybrid search** that combines two types of search:

1. **Semantic Search** (Meaning-Based):
   - Finds documents that are similar in meaning to your question
   - Uses mathematical representations (embeddings) to understand context
   - Finds relevant content even when different words are used
   - Example: Question "tax rate" finds documents mentioning "tax percentage" or "taxation level"

2. **Text Search** (Keyword-Based):
   - Finds documents containing specific keywords from your question
   - Handles typos and variations
   - Matches exact phrases and terms
   - Example: Question "VAT" finds documents containing "VAT", "value-added tax", etc.

3. **Result Merging**:
   - Combines results from both searches
   - Documents appearing in both searches get higher priority
   - Removes duplicates
   - Ranks results by relevance

#### Search Filtering

The system can filter searches by:

- **Project**: If your session is linked to a project, it prioritizes project documents
- **Document Type**: Filter by specific document types (if needed)
- **Author**: Filter by document author (if needed)
- **Date Range**: Filter by document date (if needed)

#### Number of Results

By default, the system retrieves the **top 5 most relevant document sections** (chunks) for each question. This provides enough information to answer comprehensively without overwhelming the answer.

### Step 5: Q&A History Search (Optional)

If enabled, the system also searches previous Q&A pairs:

#### When History Search is Used

- **Follow-Up Sessions**: Previous rounds' Q&A pairs are searched
- **Same Session**: Earlier questions in the current session can be referenced
- **Similar Questions**: Questions similar to ones already answered are found

#### Benefits of History Search

- **Consistency**: Ensures answers are consistent with previous responses
- **Context**: Builds on previous answers rather than starting from scratch
- **Efficiency**: Reuses relevant information from earlier work
- **Continuity**: Maintains context across multiple rounds of questions

### Step 6: Answer Generation

Using the search results, the system generates a comprehensive answer:

#### Answer Creation Process

1. **Context Assembly**: Combines information from:
   - Document search results (top 5 chunks)
   - Q&A history results (if available)
   - Company information (from session/project)
   - Previous Q&A context (for follow-up sessions)

2. **Answer Synthesis**: Uses artificial intelligence to:
   - Synthesize information from multiple sources
   - Write a coherent, comprehensive answer
   - Ensure accuracy and relevance
   - Maintain proper context

3. **Citation Generation**: For each piece of information used:
   - Identifies the source document
   - Records the document title and source
   - Links back to the original document
   - Provides citation references

#### Answer Quality Features

- **Comprehensive**: Answers draw from multiple sources when available
- **Accurate**: Based on actual document content, not general knowledge
- **Cited**: Every answer includes citations to source documents
- **Contextual**: Considers company information and project context
- **Coherent**: Written as a natural, readable response

### Step 7: Answer Storage (Senior Users Only)

For Senior users, answers are saved as Q&A pairs:

#### What Gets Saved

- **Question**: The original question text
- **Original Answer**: The initial answer generated
- **Citations**: All source documents cited
- **Question Embedding**: Mathematical representation for future searches
- **Question Index**: Order of question in the session
- **Session Link**: Association with the session
- **Timestamps**: Created and updated dates

#### Answer Editing (Senior Users)

After answers are generated:

1. **Review**: Senior users can review each answer
2. **Edit**: Answers can be edited if needed
3. **Save Changes**: Edited answers become the "final answer"
4. **Track Changes**: System tracks whether answers were edited

#### Answer Rating (Senior Users)

Senior users can rate answers:

- **Good**: Mark answers as good/helpful
- **Bad**: Mark answers as bad/needs improvement
- **Unrated**: Leave answers unrated (default)

Ratings help track answer quality and identify areas for improvement.

### Step 8: Review Generation (Senior Users)

For Senior users, the system may generate automatic reviews:

#### Review Types

- **Good**: Answer is complete and accurate
- **Needs Info**: Answer could use more information
- **Risk**: Answer may have issues or risks

#### Review Benefits

- **Quality Check**: Automatic assessment of answer quality
- **Gap Identification**: Highlights what might be missing
- **Risk Awareness**: Flags potential issues
- **Improvement Guidance**: Suggests areas for enhancement

## Expected Results

After processing questions, you should see:

- **Answers Displayed**: Each question gets a comprehensive answer
- **Citations Shown**: Source documents are listed with each answer
- **Answer Blocks**: Questions and answers organized in clear blocks
- **For Senior Users**: Answers saved and editable
- **For Junior Users**: Answers visible but not saved
- **Processing Status**: Clear indication when processing is complete

## What Information Gets Stored

### Question Processing Fields

| Field Name | Description |
|-----------|-------------|
| `question` | The question text |
| `question_index` | Order of question (1, 2, 3...) |
| `question_embedding` | Mathematical representation for search |

### Answer Fields (Senior Users)

| Field Name | Description |
|-----------|-------------|
| `original_answer` | Initial answer generated |
| `final_answer` | Final answer (may be edited) |
| `edited_answer` | Edited version (if modified) |
| `was_edited` | Whether answer was edited |
| `edited_at` | When answer was edited |

### Citation Fields

| Field Name | Description |
|-----------|-------------|
| `citations` | Array of citation objects |
| Citation `title` | Document title |
| Citation `source` | Document source/path |
| Citation `content` | Relevant content excerpt |

### Review Fields (Senior Users)

| Field Name | Description |
|-----------|-------------|
| `review` | Review information object |
| Review `status` | "good", "needs_info", or "risk" |
| Review `explanation` | Explanation of review |

### Rating Fields (Senior Users)

| Field Name | Description |
|-----------|-------------|
| `rating_good` | true (good), false (bad), or null (unrated) |
| `rated_at` | When rating was set |
| `rated_by` | Who rated (if tracked) |

### Outcome Fields

| Field Name | Description |
|-----------|-------------|
| `outcome_status` | "successful", "unsuccessful", or null |
| `session_id` | Link to the session |
| `created_at` | When Q&A pair was created |
| `updated_at` | Last update timestamp |

## Troubleshooting

### Questions Not Processing

- **Check Session**: Ensure you have an active session
- **Verify Documents**: Make sure documents are uploaded and ingested
- **Check Format**: Ensure questions are properly formatted
- **Review Errors**: Look for error messages in the interface

### Answers Seem Incomplete

- **Check Documents**: Verify relevant documents are uploaded
- **Review Citations**: Check if citations are being found
- **Try Rephrasing**: Rephrase questions to be more specific
- **Check Project Scope**: Ensure you're searching the right project's documents

### Citations Not Appearing

- **Verify Ingestion**: Ensure documents were successfully ingested
- **Check Search**: Verify documents are being found in searches
- **Review Processing**: Check if processing completed successfully

### Sub-Questions Not Created

- **Question Complexity**: Simple questions don't need decomposition
- **Decomposition Settings**: Check if decomposition is enabled
- **Question Format**: Ensure questions are clear and well-formed

### Answers Not Being Saved (Senior User)

- **Verify Role**: Ensure you're using a Senior session
- **Check Session**: Verify you're in the correct session
- **Review Permissions**: Ensure you have permission to save Q&A pairs

## Additional Information

### Question Best Practices

- **Be Specific**: Specific questions get better answers
- **One Topic Per Question**: Avoid asking multiple unrelated things
- **Use Clear Language**: Write questions clearly and concisely
- **Provide Context**: Include relevant context when helpful

### Answer Quality Tips

- **Review Citations**: Always check the source documents
- **Verify Accuracy**: Verify answers against source material
- **Edit When Needed**: Don't hesitate to edit answers for accuracy
- **Rate Answers**: Rate answers to help improve the system

### Search Optimization

- **Project Scope**: Use project-scoped documents for better relevance
- **Company Context**: Provide company information for better context
- **Follow-Up Sessions**: Use follow-up sessions to build on previous work
- **Clear Questions**: Clear, specific questions get better search results

### Performance Considerations

- **Processing Time**: Complex questions may take longer to process
- **Multiple Questions**: Processing multiple questions takes time
- **Document Volume**: More documents may increase search time
- **Network Speed**: Internet speed affects processing time

## Related Features

- **Document Ingestion**: Documents must be ingested before they can be searched
- **Session Management**: Questions are processed within sessions
- **Project Organization**: Project-scoped documents improve search relevance
- **Answer Review**: Review and edit answers (Senior users)
- **Export Functionality**: Export sessions with all Q&A pairs and citations

