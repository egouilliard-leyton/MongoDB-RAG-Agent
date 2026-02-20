import React, { useRef, useState, useCallback, DragEvent } from 'react';
import { useIngestion } from '../contexts/IngestionContext';
import { Button } from './Button';
import { ErrorAlert } from './ErrorAlert';

// =============================================================================
// Types
// =============================================================================

interface DocumentUploaderProps {
  projectId?: string;
  onUploadComplete?: () => void;
  className?: string;
}

interface FileValidation {
  valid: boolean;
  error: string | null;
}

// =============================================================================
// Constants
// =============================================================================

/**
 * Allowed file extensions and their MIME types.
 */
const ALLOWED_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.doc',
  '.pptx',
  '.xlsx',
  '.xls',
  '.html',
  '.md',
  '.txt',
] as const;

const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'text/html',
  'text/markdown',
  'text/plain',
] as const;

/**
 * Maximum file size in bytes (50MB).
 */
const MAX_FILE_SIZE = 50 * 1024 * 1024;

/**
 * Format file size for display.
 */
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// =============================================================================
// Component
// =============================================================================

/**
 * DocumentUploader component provides a file dropzone with drag-and-drop support
 * for uploading documents to the ingestion pipeline.
 *
 * Features:
 * - Drag and drop file upload
 * - File type validation
 * - File size validation
 * - Upload progress display via IngestionProgress
 * - Upload result display via IngestionResult
 */
export const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  projectId,
  onUploadComplete,
  className = '',
}) => {
  const {
    currentUpload,
    uploadDocument,
    clearCurrentUpload,
    error,
    clearError,
  } = useIngestion();

  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  /**
   * Validate a file before upload.
   */
  const validateFile = useCallback((file: File): FileValidation => {
    // Check file extension
    const extension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension as any)) {
      return {
        valid: false,
        error: `Invalid file type "${extension}". Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`,
      };
    }

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return {
        valid: false,
        error: `File too large (${formatFileSize(file.size)}). Maximum: ${formatFileSize(MAX_FILE_SIZE)}`,
      };
    }

    // Check MIME type (optional, some files may have incorrect MIME types)
    if (file.type && !ALLOWED_MIME_TYPES.includes(file.type as any)) {
      // Just warn, don't block - some systems have incorrect MIME types
      console.warn(`Unexpected MIME type: ${file.type} for file ${file.name}`);
    }

    return { valid: true, error: null };
  }, []);

  /**
   * Handle file selection from dropzone or input.
   */
  const handleFileSelect = useCallback(
    (file: File) => {
      setValidationError(null);
      clearError();

      const validation = validateFile(file);
      if (!validation.valid) {
        setValidationError(validation.error);
        return;
      }

      setSelectedFile(file);
    },
    [validateFile, clearError]
  );

  /**
   * Handle click on dropzone to open file picker.
   */
  const handleClick = () => {
    inputRef.current?.click();
  };

  /**
   * Handle file input change event.
   */
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    // Reset input so same file can be selected again
    e.target.value = '';
  };

  /**
   * Handle drag enter event.
   */
  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  /**
   * Handle drag leave event.
   */
  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set isDragging to false if leaving the dropzone entirely
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  /**
   * Handle drag over event (required for drop to work).
   */
  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  /**
   * Handle drop event.
   */
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  /**
   * Start the upload process.
   */
  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      await uploadDocument(selectedFile, projectId);
      setSelectedFile(null);
      onUploadComplete?.();
    } catch {
      // Error handled by context
    }
  };

  /**
   * Cancel selected file.
   */
  const handleCancel = () => {
    setSelectedFile(null);
    setValidationError(null);
    clearError();
  };

  /**
   * Clear upload result and start fresh.
   */
  const handleUploadAnother = () => {
    clearCurrentUpload();
    setSelectedFile(null);
    setValidationError(null);
  };

  // Show upload result if completed
  if (currentUpload?.isComplete && currentUpload.result) {
    return (
      <div className={`space-y-4 ${className}`}>
        <UploadResult
          result={currentUpload.result}
          onUploadAnother={handleUploadAnother}
        />
      </div>
    );
  }

  // Show upload error if failed
  if (currentUpload?.isComplete && currentUpload.error) {
    return (
      <div className={`space-y-4 ${className}`}>
        <ErrorAlert
          message={currentUpload.error}
          onDismiss={handleUploadAnother}
        />
        <Button variant="outline" onClick={handleUploadAnother}>
          Try Again
        </Button>
      </div>
    );
  }

  // Show progress if uploading
  if (currentUpload?.isUploading) {
    return (
      <div className={`space-y-4 ${className}`}>
        <UploadProgress filename={currentUpload.file.name} />
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* File Dropzone */}
      <div
        onClick={handleClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={handleInputChange}
        />

        {/* Upload Icon */}
        <div className="mb-4">
          <svg
            className={`mx-auto h-12 w-12 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`}
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Instructions */}
        <div className="space-y-2">
          <p className="text-sm text-gray-600">
            {isDragging ? (
              <span className="text-blue-600 font-medium">Drop file here</span>
            ) : (
              <>
                <span className="text-blue-600 font-medium">Click to upload</span>
                {' or drag and drop'}
              </>
            )}
          </p>
          <p className="text-xs text-gray-500">
            {ALLOWED_EXTENSIONS.join(', ').toUpperCase()} up to {formatFileSize(MAX_FILE_SIZE)}
          </p>
        </div>
      </div>

      {/* Validation Error */}
      {validationError && (
        <ErrorAlert message={validationError} onDismiss={() => setValidationError(null)} />
      )}

      {/* API Error */}
      {error && <ErrorAlert message={error} onDismiss={clearError} />}

      {/* Selected File Preview */}
      {selectedFile && (
        <SelectedFilePreview
          file={selectedFile}
          onUpload={handleUpload}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface SelectedFilePreviewProps {
  file: File;
  onUpload: () => void;
  onCancel: () => void;
}

/**
 * Preview of selected file with upload/cancel actions.
 */
const SelectedFilePreview: React.FC<SelectedFilePreviewProps> = ({
  file,
  onUpload,
  onCancel,
}) => {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {/* File Icon */}
          <div className="flex-shrink-0">
            <FileIcon filename={file.name} />
          </div>

          {/* File Info */}
          <div>
            <p className="text-sm font-medium text-gray-900 truncate max-w-xs">
              {file.name}
            </p>
            <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={onUpload}>
            Upload
          </Button>
        </div>
      </div>
    </div>
  );
};

interface UploadProgressProps {
  filename: string;
}

/**
 * Simple upload progress indicator.
 * The full IngestionProgress component will replace this with stage tracking.
 */
const UploadProgress: React.FC<UploadProgressProps> = ({ filename }) => {
  return (
    <div className="bg-blue-50 rounded-lg p-6">
      <div className="flex items-center space-x-4">
        {/* Spinner */}
        <div className="flex-shrink-0">
          <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
        </div>

        {/* Status */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-blue-900">Uploading and processing...</p>
          <p className="text-xs text-blue-700 truncate">{filename}</p>
        </div>
      </div>
    </div>
  );
};

interface UploadResultProps {
  result: {
    document_id: string | null;
    title: string;
    filename: string;
    status: string;
    chunks_created: number;
    total_tokens: number;
    metadata_extracted: Record<string, any>;
    warnings: string[];
    errors: string[];
    processing_time_ms: number;
  };
  onUploadAnother: () => void;
}

/**
 * Display upload result summary.
 * The full IngestionResult component will provide more detailed display.
 */
const UploadResult: React.FC<UploadResultProps> = ({ result, onUploadAnother }) => {
  const isSuccess = result.status === 'success';
  const isPartial = result.status === 'partial';

  return (
    <div
      className={`rounded-lg p-6 ${
        isSuccess
          ? 'bg-green-50 border border-green-200'
          : isPartial
          ? 'bg-yellow-50 border border-yellow-200'
          : 'bg-red-50 border border-red-200'
      }`}
    >
      {/* Header */}
      <div className="flex items-start space-x-3 mb-4">
        <div className="flex-shrink-0">
          {isSuccess ? (
            <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : isPartial ? (
            <svg className="w-6 h-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          ) : (
            <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
        </div>
        <div>
          <h3 className={`text-lg font-medium ${isSuccess ? 'text-green-900' : isPartial ? 'text-yellow-900' : 'text-red-900'}`}>
            {isSuccess ? 'Document Ingested Successfully' : isPartial ? 'Document Partially Ingested' : 'Ingestion Failed'}
          </h3>
          <p className="text-sm text-gray-600 mt-1">{result.title || result.filename}</p>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{result.chunks_created}</p>
          <p className="text-xs text-gray-500">Chunks Created</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{result.total_tokens.toLocaleString()}</p>
          <p className="text-xs text-gray-500">Total Tokens</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-900">{(result.processing_time_ms / 1000).toFixed(1)}s</p>
          <p className="text-xs text-gray-500">Processing Time</p>
        </div>
      </div>

      {/* Metadata Extracted */}
      {Object.keys(result.metadata_extracted).length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Metadata Extracted</h4>
          <div className="bg-white rounded p-3 text-xs">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
              {Object.entries(result.metadata_extracted)
                .filter(([, value]) => value !== null && value !== undefined && value !== '')
                .slice(0, 6) // Show first 6 items
                .map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt className="text-gray-500 truncate">{formatMetadataKey(key)}</dt>
                    <dd className="text-gray-900 truncate">{formatMetadataValue(value)}</dd>
                  </React.Fragment>
                ))}
            </dl>
          </div>
        </div>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-yellow-700 mb-1">Warnings</h4>
          <ul className="text-xs text-yellow-600 space-y-1">
            {result.warnings.map((warning, i) => (
              <li key={i} className="flex items-start">
                <span className="mr-1">-</span>
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Errors */}
      {result.errors.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-red-700 mb-1">Errors</h4>
          <ul className="text-xs text-red-600 space-y-1">
            {result.errors.map((error, i) => (
              <li key={i} className="flex items-start">
                <span className="mr-1">-</span>
                <span>{error}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end space-x-2">
        <Button variant="outline" size="sm" onClick={onUploadAnother}>
          Upload Another
        </Button>
      </div>
    </div>
  );
};

// =============================================================================
// Helper Components
// =============================================================================

interface FileIconProps {
  filename: string;
}

/**
 * File type icon based on extension.
 */
const FileIcon: React.FC<FileIconProps> = ({ filename }) => {
  const extension = filename.split('.').pop()?.toLowerCase();

  // Color mapping for file types
  const colorClass = (() => {
    switch (extension) {
      case 'pdf':
        return 'text-red-500';
      case 'doc':
      case 'docx':
        return 'text-blue-500';
      case 'pptx':
        return 'text-orange-500';
      case 'xlsx':
      case 'xls':
        return 'text-green-500';
      case 'html':
        return 'text-purple-500';
      case 'md':
        return 'text-gray-700';
      case 'txt':
        return 'text-gray-500';
      default:
        return 'text-gray-400';
    }
  })();

  return (
    <svg className={`w-10 h-10 ${colorClass}`} fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
        clipRule="evenodd"
      />
    </svg>
  );
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format metadata key for display (snake_case to Title Case).
 */
const formatMetadataKey = (key: string): string => {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Format metadata value for display.
 */
const formatMetadataValue = (value: any): string => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

export default DocumentUploader;
