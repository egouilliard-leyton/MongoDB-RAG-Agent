# How Document Ingestion Works

This guide explains how documents are processed and stored in the system when you upload them. Understanding this process helps you know what information is captured and how documents become searchable.

> **Visual Diagram**: A flow diagram showing the complete document ingestion process is available in Excalidraw. The diagram illustrates each step from document upload through metadata extraction, chunking, embedding generation, and final storage in the database.

## Introduction

When you upload a document (PDF, Word, PowerPoint, Excel, or other supported formats), the system automatically extracts important information, breaks the document into searchable pieces, and stores everything in a way that makes it easy to find relevant content when answering questions.

## Prerequisites

- A document file ready to upload (PDF, DOCX, PPTX, XLSX, or other supported formats)
- Access to the project upload feature in the application
- A project created and selected (for project-scoped uploads)

## What Happens During Document Ingestion

### Step 1: Document Upload

When you upload a document through the application:

1. The system receives your file
2. It identifies the file type (PDF, Word document, etc.)
3. It prepares the file for processing

### Step 2: Content Extraction

The system reads the entire document and converts it into text format. This process:

- Preserves the document structure (headings, paragraphs, sections)
- Extracts text from all pages
- Maintains formatting information where useful
- Handles complex documents with tables, images, and special layouts

### Step 3: Metadata Extraction

The system automatically identifies and extracts important information from your document. This includes:

#### Document Identification Information

- **Document ID** (`id_informacji`): A unique identifier for the document
- **Signature** (`sygnatura`): The official document signature or reference number
- **Document Type** (`document_type`): The category of document (e.g., KDIP2, KDIB1-3)
- **Document Date** (`document_date`): The date when the document was created
- **Document Number** (`document_number`): The document's reference number

#### Document Content Information

- **Title/Question** (`tytul_teza`): The main title or question the document addresses
- **Author** (`author`): The person or organization who created the document
- **Keywords** (`slowa_kluczowe`): Important terms and topics covered in the document
- **Category** (`kategoria`): The category classification (e.g., "Interpretacja indywidualna")
- **Status** (`status`): The current status of the document (e.g., "Aktualna")

#### Business Outcome Information

- **Outcome Status** (`outcome_status`): Whether the interpretation or decision was "successful" or "unsuccessful"
- **Interpretation Stance** (`interpretation_stance`): Whether the stance is "positive", "partial", or "negative"
- **Outcome Paragraphs** (`outcome_paragraphs`): Specific sections that explain the outcome

#### File Information

- **File Path**: Where the document is stored
- **File Size**: Size of the original file
- **Ingestion Date**: When the document was processed
- **Line Count**: Number of lines in the document
- **Word Count**: Total number of words
- **Section Count**: Number of major sections or headings

### Step 4: Document Chunking

The system breaks the document into smaller, searchable pieces called "chunks." This process:

- Preserves document structure and context
- Creates chunks that are the right size for searching
- Ensures important information isn't split awkwardly
- Maintains relationships between related sections

**Why chunking is important**: Instead of searching through entire documents, the system can quickly find the specific sections that answer your questions.

### Step 5: Embedding Generation

For each chunk, the system creates a mathematical representation (called an "embedding") that captures the meaning of the text. This allows the system to:

- Find documents that are similar in meaning, not just exact word matches
- Understand the context and intent behind questions
- Match questions to relevant document sections even when different words are used

### Step 6: Database Storage

The system stores everything in two main collections:

#### Documents Collection

Stores the complete document with all its information:

- **Full document content**: The entire text of the document
- **Title**: The document title
- **Source**: The file path or location
- **Metadata**: All extracted information (IDs, dates, keywords, outcomes, etc.)
- **Created date**: When the document was ingested

#### Chunks Collection

Stores the searchable pieces of each document:

- **Content**: The text content of this specific chunk
- **Embedding**: The mathematical representation for semantic search
- **Document ID**: Link back to the parent document
- **Chunk Index**: The position of this chunk in the document
- **Metadata**: Important document information copied to the chunk (for filtering)
  - Project ID (if document belongs to a project)
  - Document type
  - Document date
  - Author
  - Keywords
  - Outcome status
  - Interpretation stance

**Why two collections?**: 
- The Documents collection stores complete information for reference
- The Chunks collection stores searchable pieces that can be quickly found and matched to questions

## Expected Results

After ingestion is complete, you should see:

- A success message confirming the document was processed
- The document appears in your project's document list
- The document becomes searchable when you ask questions
- All extracted metadata is stored and can be used for filtering searches

## What Information Gets Stored

### Complete List of Stored Fields

#### Document-Level Fields

| Field Name | Description | Example |
|-----------|-------------|---------|
| `id_informacji` | Unique document identifier | "12345" |
| `sygnatura` | Official document signature | "KDIP2-1.4010.514.2025.2.DK" |
| `document_type` | Type/category of document | "KDIP2" or "KDIB1-3" |
| `document_date` | Date document was created | "2025-11-17" |
| `document_number` | Document reference number | "1.4010.514.2025.2" |
| `tytul_teza` | Main title or question | "Tax treatment of..." |
| `author` | Document author | "DK" or "JMS" |
| `slowa_kluczowe` | Keywords/tags | ["tax", "interpretation", "VAT"] |
| `kategoria` | Document category | "Interpretacja indywidualna" |
| `status` | Current status | "Aktualna" |
| `outcome_status` | Success/unsuccess status | "successful" or "unsuccessful" |
| `interpretation_stance` | Positive/partial/negative | "positive", "partial", or "negative" |
| `outcome_paragraphs` | Relevant outcome sections | ["Paragraph text..."] |
| `file_path` | File location | "documents/file.pdf" |
| `file_size` | File size in bytes | 245678 |
| `ingestion_date` | When processed | "2025-01-15T10:30:00" |
| `line_count` | Number of lines | 1250 |
| `word_count` | Number of words | 8500 |
| `section_count` | Number of sections | 12 |

#### Chunk-Level Fields

| Field Name | Description |
|-----------|-------------|
| `content` | The text content of this chunk |
| `embedding` | Mathematical representation for search |
| `document_id` | Link to parent document |
| `chunk_index` | Position in document (0, 1, 2...) |
| `token_count` | Number of tokens in chunk |
| `metadata` | Copied document metadata for filtering |

## Troubleshooting

### Document Not Appearing After Upload

- **Check upload status**: Look for error messages in the upload interface
- **Verify file format**: Ensure the file is in a supported format (PDF, DOCX, PPTX, etc.)
- **Check project selection**: Make sure you have a project selected when uploading
- **Review file size**: Very large files may take longer to process

### Missing Metadata

- **Document format**: Some metadata fields are specific to certain document types (e.g., tax interpretation documents)
- **Document structure**: If the document doesn't follow expected formats, some metadata may not be extracted
- **Filename pattern**: Some metadata comes from the filename - ensure it follows the expected pattern

### Documents Not Found in Searches

- **Wait for processing**: Large documents may take a few moments to become searchable
- **Check project scope**: If searching within a project, ensure documents were uploaded to that project
- **Verify ingestion success**: Check that the document appears in the project's document list

## Additional Information

### Project-Scoped Documents

When you upload documents to a specific project:

- Documents are tagged with the project ID
- Searches within that project's sessions will prioritize project documents
- Documents can be filtered by project when searching

### Document Updates

- If you upload the same document again, it will create a new entry (not update the existing one)
- To update a document, you may need to remove the old version first
- Each upload creates a new document record with a new timestamp

### Supported File Formats

The system supports multiple file formats:

- **PDF** (.pdf): Most common format
- **Word Documents** (.docx): Microsoft Word files
- **PowerPoint** (.pptx): Presentation files
- **Excel** (.xlsx): Spreadsheet files
- **Markdown** (.md): Text files with formatting
- **HTML** (.html): Web pages
- **Audio files**: Can be transcribed and processed

### Performance Considerations

- **Large documents**: Documents with many pages may take longer to process
- **Complex layouts**: Documents with complex tables or graphics may require more processing time
- **Batch uploads**: Multiple documents can be uploaded, but each is processed individually

## Related Features

- **Project Management**: Documents are organized by projects
- **Question Processing**: Ingested documents are used to answer questions
- **Search Functionality**: The chunking and embedding process enables powerful search capabilities
- **Document Filtering**: Metadata allows filtering searches by document type, date, author, etc.

