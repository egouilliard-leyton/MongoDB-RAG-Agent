import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  ReactNode,
} from 'react';
import type {
  Document,
  DocumentFilter,
} from '../api/types';
import * as api from '../api/client';

// =============================================================================
// Types
// =============================================================================

/**
 * Context value exposed by DocumentProvider.
 */
interface DocumentContextType {
  // Documents list
  documents: Document[];
  documentsTotal: number;
  hasMoreDocuments: boolean;

  // Loading states
  isLoadingDocuments: boolean;

  // Error state
  error: string | null;

  // Actions
  loadDocuments: (
    filters?: DocumentFilter,
    limit?: number,
    skip?: number
  ) => Promise<void>;
  loadMoreDocuments: (filters?: DocumentFilter) => Promise<void>;
  refreshDocuments: (filters?: DocumentFilter) => Promise<void>;
  getDocument: (id: string) => Promise<Document>;
  deleteDocument: (id: string) => Promise<void>;

  clearError: () => void;
}

// =============================================================================
// Context
// =============================================================================

const DocumentContext = createContext<DocumentContextType | undefined>(
  undefined
);

/**
 * Hook to access the document context.
 * Must be used within a DocumentProvider.
 */
export const useDocuments = (): DocumentContextType => {
  const context = useContext(DocumentContext);
  if (!context) {
    throw new Error('useDocuments must be used within a DocumentProvider');
  }
  return context;
};

// =============================================================================
// Provider
// =============================================================================

interface DocumentProviderProps {
  children: ReactNode;
}

/**
 * Provider component for document state management.
 * Manages document list, pagination, and CRUD operations.
 */
export const DocumentProvider: React.FC<DocumentProviderProps> = ({
  children,
}) => {
  // Documents list state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentsTotal, setDocumentsTotal] = useState<number>(0);
  const [hasMoreDocuments, setHasMoreDocuments] = useState<boolean>(false);
  const [currentDocumentsSkip, setCurrentDocumentsSkip] = useState<number>(0);

  // Loading states
  const [isLoadingDocuments, setIsLoadingDocuments] = useState<boolean>(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  /**
   * Load documents with optional filtering and pagination.
   */
  const loadDocuments = useCallback(
    async (
      filters?: DocumentFilter,
      limit: number = 50,
      skip: number = 0
    ): Promise<void> => {
      setIsLoadingDocuments(true);
      setError(null);

      try {
        const response = await api.getDocuments(filters, limit, skip);
        setDocuments(response.documents);
        setDocumentsTotal(response.total);
        setHasMoreDocuments(response.has_more);
        setCurrentDocumentsSkip(skip);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load documents';
        setError(message);
        throw err;
      } finally {
        setIsLoadingDocuments(false);
      }
    },
    []
  );

  /**
   * Load more documents (pagination).
   */
  const loadMoreDocuments = useCallback(
    async (filters?: DocumentFilter): Promise<void> => {
      if (!hasMoreDocuments || isLoadingDocuments) return;

      const newSkip = currentDocumentsSkip + 50;
      setIsLoadingDocuments(true);
      setError(null);

      try {
        const response = await api.getDocuments(filters, 50, newSkip);
        setDocuments((prev) => [...prev, ...response.documents]);
        setDocumentsTotal(response.total);
        setHasMoreDocuments(response.has_more);
        setCurrentDocumentsSkip(newSkip);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load more documents';
        setError(message);
        throw err;
      } finally {
        setIsLoadingDocuments(false);
      }
    },
    [hasMoreDocuments, isLoadingDocuments, currentDocumentsSkip]
  );

  /**
   * Refresh documents list (reload from beginning).
   */
  const refreshDocuments = useCallback(
    async (filters?: DocumentFilter): Promise<void> => {
      await loadDocuments(filters, 50, 0);
    },
    [loadDocuments]
  );

  /**
   * Get a single document by ID.
   */
  const getDocument = useCallback(async (id: string): Promise<Document> => {
    try {
      return await api.getDocument(id);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to get document';
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Delete a document and all its associated chunks.
   */
  const deleteDocument = useCallback(async (id: string): Promise<void> => {
    try {
      await api.deleteDocument(id);
      // Remove from local state
      setDocuments((prev) => prev.filter((doc) => doc._id !== id));
      setDocumentsTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to delete document';
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Clear error state.
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Context value
  const value: DocumentContextType = {
    documents,
    documentsTotal,
    hasMoreDocuments,
    isLoadingDocuments,
    error,
    loadDocuments,
    loadMoreDocuments,
    refreshDocuments,
    getDocument,
    deleteDocument,
    clearError,
  };

  return (
    <DocumentContext.Provider value={value}>{children}</DocumentContext.Provider>
  );
};
