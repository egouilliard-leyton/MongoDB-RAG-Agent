import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from 'react';
import type {
  IngestionJob,
  IngestionProgress,
  IngestionJobFilter,
  IngestionAggregateStats,
  DocumentUploadResponse,
} from '../api/types';
import * as api from '../api/client';

// =============================================================================
// Types
// =============================================================================

/**
 * Current upload state tracked during file upload and ingestion.
 */
interface CurrentUpload {
  file: File;
  jobId: string | null;
  progress: IngestionProgress | null;
  result: DocumentUploadResponse | null;
  error: string | null;
  isUploading: boolean;
  isComplete: boolean;
}

/**
 * Context value exposed by IngestionProvider.
 */
interface IngestionContextType {
  // Current upload state
  currentUpload: CurrentUpload | null;

  // Ingestion history
  jobs: IngestionJob[];
  jobsTotal: number;
  hasMoreJobs: boolean;

  // Aggregate stats
  stats: IngestionAggregateStats | null;

  // Loading states
  isLoadingJobs: boolean;
  isLoadingStats: boolean;

  // Error state
  error: string | null;

  // Actions
  uploadDocument: (file: File, projectId?: string) => Promise<DocumentUploadResponse>;
  cancelUpload: () => void;
  clearCurrentUpload: () => void;

  loadJobs: (filters?: IngestionJobFilter, limit?: number, skip?: number) => Promise<void>;
  loadMoreJobs: (filters?: IngestionJobFilter) => Promise<void>;
  refreshJobs: (filters?: IngestionJobFilter) => Promise<void>;
  getJob: (jobId: string) => Promise<IngestionJob>;
  deleteJob: (jobId: string) => Promise<void>;

  loadStats: (projectId?: string) => Promise<void>;

  clearError: () => void;
}

// =============================================================================
// Context
// =============================================================================

const IngestionContext = createContext<IngestionContextType | undefined>(undefined);

/**
 * Hook to access the ingestion context.
 * Must be used within an IngestionProvider.
 */
export const useIngestion = (): IngestionContextType => {
  const context = useContext(IngestionContext);
  if (!context) {
    throw new Error('useIngestion must be used within an IngestionProvider');
  }
  return context;
};

// =============================================================================
// Provider
// =============================================================================

interface IngestionProviderProps {
  children: ReactNode;
}

/**
 * Provider component for ingestion state management.
 * Manages current upload state, ingestion job history, and aggregate statistics.
 */
export const IngestionProvider: React.FC<IngestionProviderProps> = ({ children }) => {
  // Current upload state
  const [currentUpload, setCurrentUpload] = useState<CurrentUpload | null>(null);

  // Jobs list state
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [jobsTotal, setJobsTotal] = useState<number>(0);
  const [hasMoreJobs, setHasMoreJobs] = useState<boolean>(false);
  const [currentJobsSkip, setCurrentJobsSkip] = useState<number>(0);

  // Stats state
  const [stats, setStats] = useState<IngestionAggregateStats | null>(null);

  // Loading states
  const [isLoadingJobs, setIsLoadingJobs] = useState<boolean>(false);
  const [isLoadingStats, setIsLoadingStats] = useState<boolean>(false);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Ref for SSE cleanup function
  const sseCleanupRef = useRef<(() => void) | null>(null);

  /**
   * Upload a document with real-time progress tracking via SSE.
   */
  const uploadDocument = useCallback(
    async (file: File, projectId?: string): Promise<DocumentUploadResponse> => {
      // Clean up any existing SSE connection
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
        sseCleanupRef.current = null;
      }

      // Initialize upload state
      setCurrentUpload({
        file,
        jobId: null,
        progress: null,
        result: null,
        error: null,
        isUploading: true,
        isComplete: false,
      });
      setError(null);

      try {
        // Start the upload
        const result = await api.uploadDocument(file, projectId);

        // Log the result for debugging
        console.log('[IngestionContext] Upload result received:', {
          status: result.status,
          job_id: result.job_id,
          document_id: result.document_id,
          chunks_created: result.chunks_created,
          total_tokens: result.total_tokens,
          processing_time_ms: result.processing_time_ms,
          errors: result.errors,
          warnings: result.warnings,
        });

        // Update state with result
        setCurrentUpload((prev) =>
          prev
            ? {
                ...prev,
                jobId: result.job_id,
                result,
                isUploading: false,
                isComplete: true,
              }
            : null
        );

        return result;
      } catch (err) {
        console.error('[IngestionContext] Upload error:', err);
        const message = err instanceof Error ? err.message : 'Failed to upload document';
        setCurrentUpload((prev) =>
          prev
            ? {
                ...prev,
                error: message,
                isUploading: false,
                isComplete: true,
              }
            : null
        );
        setError(message);
        throw err;
      }
    },
    []
  );

  /**
   * Cancel the current upload (closes SSE connection).
   */
  const cancelUpload = useCallback(() => {
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
      sseCleanupRef.current = null;
    }
    setCurrentUpload((prev) =>
      prev
        ? {
            ...prev,
            isUploading: false,
            error: 'Upload cancelled',
          }
        : null
    );
  }, []);

  /**
   * Clear the current upload state.
   */
  const clearCurrentUpload = useCallback(() => {
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
      sseCleanupRef.current = null;
    }
    setCurrentUpload(null);
  }, []);

  /**
   * Load ingestion jobs with optional filtering and pagination.
   */
  const loadJobs = useCallback(
    async (filters?: IngestionJobFilter, limit: number = 50, skip: number = 0): Promise<void> => {
      setIsLoadingJobs(true);
      setError(null);

      try {
        const response = await api.getIngestionJobs(filters, limit, skip);
        setJobs(response.jobs);
        setJobsTotal(response.total);
        setHasMoreJobs(response.has_more);
        setCurrentJobsSkip(skip);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load ingestion jobs';
        setError(message);
        throw err;
      } finally {
        setIsLoadingJobs(false);
      }
    },
    []
  );

  /**
   * Load more jobs (pagination).
   */
  const loadMoreJobs = useCallback(
    async (filters?: IngestionJobFilter): Promise<void> => {
      if (!hasMoreJobs || isLoadingJobs) return;

      const newSkip = currentJobsSkip + 50;
      setIsLoadingJobs(true);
      setError(null);

      try {
        const response = await api.getIngestionJobs(filters, 50, newSkip);
        setJobs((prev) => [...prev, ...response.jobs]);
        setJobsTotal(response.total);
        setHasMoreJobs(response.has_more);
        setCurrentJobsSkip(newSkip);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load more jobs';
        setError(message);
        throw err;
      } finally {
        setIsLoadingJobs(false);
      }
    },
    [hasMoreJobs, isLoadingJobs, currentJobsSkip]
  );

  /**
   * Refresh jobs list (reload from beginning).
   */
  const refreshJobs = useCallback(
    async (filters?: IngestionJobFilter): Promise<void> => {
      await loadJobs(filters, 50, 0);
    },
    [loadJobs]
  );

  /**
   * Get a single job by ID.
   */
  const getJob = useCallback(async (jobId: string): Promise<IngestionJob> => {
    try {
      return await api.getIngestionJob(jobId);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get ingestion job';
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Delete a job record.
   */
  const deleteJob = useCallback(async (jobId: string): Promise<void> => {
    try {
      await api.deleteIngestionJob(jobId);
      // Remove from local state
      setJobs((prev) => prev.filter((job) => job._id !== jobId));
      setJobsTotal((prev) => Math.max(0, prev - 1));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete job';
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Load aggregate statistics.
   */
  const loadStats = useCallback(async (projectId?: string): Promise<void> => {
    setIsLoadingStats(true);
    setError(null);

    try {
      const response = await api.getIngestionStats(projectId);
      setStats(response.stats);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load statistics';
      setError(message);
      throw err;
    } finally {
      setIsLoadingStats(false);
    }
  }, []);

  /**
   * Clear error state.
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Context value
  const value: IngestionContextType = {
    currentUpload,
    jobs,
    jobsTotal,
    hasMoreJobs,
    stats,
    isLoadingJobs,
    isLoadingStats,
    error,
    uploadDocument,
    cancelUpload,
    clearCurrentUpload,
    loadJobs,
    loadMoreJobs,
    refreshJobs,
    getJob,
    deleteJob,
    loadStats,
    clearError,
  };

  return <IngestionContext.Provider value={value}>{children}</IngestionContext.Provider>;
};
