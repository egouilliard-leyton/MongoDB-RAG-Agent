import React, { useEffect, useState, useCallback } from 'react';
import { useDocuments } from '../contexts/DocumentContext';
import type { Document, DocumentFilter } from '../api/types';
import { Button } from './Button';
import { LoadingSpinner } from './LoadingSpinner';
import { ErrorAlert } from './ErrorAlert';

// =============================================================================
// Types
// =============================================================================

interface DocumentListProps {
  projectId?: string;
  onDocumentClick?: (document: Document) => void;
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

/**
 * DocumentList provides a comprehensive view of all documents
 * with filtering, search, and pagination.
 *
 * Features:
 * - Search by title/filename
 * - Filter by project_id (if provided)
 * - Paginated document list with click-through
 * - Refresh and load more functionality
 */
export const DocumentList: React.FC<DocumentListProps> = ({
  projectId,
  onDocumentClick,
  className = '',
}) => {
  const {
    documents,
    documentsTotal,
    hasMoreDocuments,
    isLoadingDocuments,
    error,
    loadDocuments,
    loadMoreDocuments,
    clearError,
  } = useDocuments();

  // Filter state
  const [filters, setFilters] = useState<DocumentFilter>({
    project_id: projectId,
  });
  const [searchQuery, setSearchQuery] = useState('');

  // Initial load
  useEffect(() => {
    loadDocuments({ project_id: projectId });
  }, [projectId, loadDocuments]);

  /**
   * Apply filters and reload documents.
   */
  const applyFilters = useCallback(() => {
    const newFilters: DocumentFilter = {
      project_id: projectId,
    };

    if (searchQuery.trim()) {
      newFilters.search = searchQuery.trim();
    }

    setFilters(newFilters);
    loadDocuments(newFilters);
  }, [projectId, searchQuery, loadDocuments]);

  /**
   * Clear all filters and reload.
   */
  const clearFilters = useCallback(() => {
    setSearchQuery('');
    const newFilters = { project_id: projectId };
    setFilters(newFilters);
    loadDocuments(newFilters);
  }, [projectId, loadDocuments]);

  /**
   * Handle refresh button click.
   */
  const handleRefresh = useCallback(() => {
    loadDocuments(filters);
  }, [filters, loadDocuments]);

  /**
   * Handle load more button click.
   */
  const handleLoadMore = useCallback(() => {
    loadMoreDocuments(filters);
  }, [filters, loadMoreDocuments]);

  // Check if any filters are active
  const hasActiveFilters = searchQuery.trim() !== '';

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">All Documents</h2>
          <p className="text-sm text-gray-500">
            {documentsTotal} total document{documentsTotal !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isLoadingDocuments}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && <ErrorAlert message={error} onDismiss={clearError} />}

      {/* Filters */}
      <FiltersSection
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onApply={applyFilters}
        onClear={clearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Document List */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {isLoadingDocuments && documents.length === 0 ? (
          <div className="p-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : documents.length === 0 ? (
          <EmptyState
            hasFilters={hasActiveFilters}
            onClearFilters={clearFilters}
          />
        ) : (
          <>
            <DocumentListContent
              documents={documents}
              onDocumentClick={onDocumentClick}
            />
            {hasMoreDocuments && (
              <div className="p-4 border-t border-gray-200 text-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMore}
                  disabled={isLoadingDocuments}
                  isLoading={isLoadingDocuments}
                >
                  Load More
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Sub-components
// =============================================================================

interface FiltersSectionProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onApply: () => void;
  onClear: () => void;
  hasActiveFilters: boolean;
}

/**
 * Filters section with search.
 */
const FiltersSection: React.FC<FiltersSectionProps> = ({
  searchQuery,
  onSearchChange,
  onApply,
  onClear,
  hasActiveFilters,
}) => {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Search */}
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Search Documents
          </label>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by title or filename..."
            className="w-full rounded-md border-gray-300 shadow-sm text-sm focus:border-blue-500 focus:ring-blue-500"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onApply();
              }
            }}
          />
        </div>
      </div>

      {/* Filter Actions */}
      <div className="flex justify-end space-x-2 mt-4">
        {hasActiveFilters && (
          <Button variant="outline" size="sm" onClick={onClear}>
            Clear Filters
          </Button>
        )}
        <Button variant="primary" size="sm" onClick={onApply}>
          Apply Filters
        </Button>
      </div>
    </div>
  );
};

interface DocumentListContentProps {
  documents: Document[];
  onDocumentClick?: (document: Document) => void;
}

/**
 * List of documents.
 */
const DocumentListContent: React.FC<DocumentListContentProps> = ({
  documents,
  onDocumentClick,
}) => {
  return (
    <div className="divide-y divide-gray-200">
      {documents.map((document) => (
        <DocumentRow
          key={document._id}
          document={document}
          onClick={onDocumentClick}
        />
      ))}
    </div>
  );
};

interface DocumentRowProps {
  document: Document;
  onClick?: (document: Document) => void;
}

/**
 * Individual document row in the list.
 */
const DocumentRow: React.FC<DocumentRowProps> = ({ document, onClick }) => {
  const handleClick = () => onClick?.(document);

  return (
    <div
      className={`p-4 hover:bg-gray-50 transition-colors ${
        onClick ? 'cursor-pointer' : ''
      }`}
      onClick={onClick ? handleClick : undefined}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4 min-w-0 flex-1">
          {/* Document Info */}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-gray-900 truncate">
              {document.title}
            </p>
            <div className="flex items-center space-x-3 mt-1">
              <p className="text-xs text-gray-500 truncate">
                {document.source}
              </p>
              <span className="text-xs text-gray-400">•</span>
              <p className="text-xs text-gray-500">
                {formatDate(document.created_at)}
              </p>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center space-x-6 text-sm text-gray-500 ml-4">
          <div className="text-center">
            <p className="font-medium text-gray-900">
              {document.chunk_count.toLocaleString()}
            </p>
            <p className="text-xs">chunks</p>
          </div>
          {document.project_id && (
            <div className="text-center">
              <p className="text-xs text-gray-500">Project</p>
              <p className="text-xs font-medium text-gray-700 truncate max-w-[100px]">
                {document.project_id}
              </p>
            </div>
          )}
          {onClick && (
            <svg
              className="w-5 h-5 text-gray-400 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          )}
        </div>
      </div>
    </div>
  );
};

interface EmptyStateProps {
  hasFilters: boolean;
  onClearFilters: () => void;
}

/**
 * Empty state when no documents found.
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  hasFilters,
  onClearFilters,
}) => {
  return (
    <div className="p-12 text-center">
      <svg
        className="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <h3 className="mt-4 text-sm font-medium text-gray-900">
        {hasFilters ? 'No matching documents' : 'No documents'}
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        {hasFilters
          ? 'Try adjusting your filters or clear them to see all documents.'
          : 'Upload a document to get started.'}
      </p>
      <div className="mt-6">
        {hasFilters && (
          <Button variant="outline" size="sm" onClick={onClearFilters}>
            Clear Filters
          </Button>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format date for display.
 */
const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return `Today at ${date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    })}`;
  }
  if (diffDays === 1) {
    return `Yesterday at ${date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    })}`;
  }
  if (diffDays < 7) {
    return `${diffDays} days ago`;
  }
  return date.toLocaleDateString();
};

export default DocumentList;
