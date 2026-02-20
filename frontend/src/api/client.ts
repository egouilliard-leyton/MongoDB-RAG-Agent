import axios, { AxiosError } from 'axios';
import { APIError } from './types';
import type {
  QASession,
  QAPair,
  CreateSessionRequest,
  ProcessQuestionsRequest,
  ProcessQuestionsResponse,
  UpdateAnswerRequest,
  UpdateQAPairRatingRequest,
  FollowUpSessionRequest,
  Project,
  CreateProjectRequest,
  UpdateProjectStageRequest,
  APIErrorResponse,
  // Ingestion types
  IngestionJob,
  IngestionJobListResponse,
  IngestionJobFilter,
  IngestionStatsResponse,
  IngestionProgress,
  // Document types
  Document,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentFilter,
  // System types
  HealthCheckResponse,
  IndexStatusResponse,
  DocumentVerificationResult,
  // Reference data types
  TaxOffice,
  Region,
  Industry,
  // Dashboard types
  DashboardSummary,
  RegionDistribution,
  IndustryDistribution,
  TaxOfficeDistribution,
  TrendsResponse,
  QualityMetricsResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// -----------------------------------------------------------------------------
// Normalization helpers
// -----------------------------------------------------------------------------
// Some backend responses historically returned `qa_pair_id` while `_id` was null.
// The UI (rating/edit) requires a stable `_id`, so we normalize here.
const normalizeQAPair = (raw: any): QAPair => {
  const hasStringId = (v: any): v is string => typeof v === 'string' && v.length > 0;
  const normalizedId = hasStringId(raw?._id)
    ? raw._id
    : hasStringId(raw?.qa_pair_id)
      ? raw.qa_pair_id
      : null;

  if (!normalizedId) {
    console.warn('[api] QAPair missing id (`_id`/`qa_pair_id`)', raw);
    return raw as QAPair;
  }

  return {
    ...raw,
    _id: normalizedId,
  } as QAPair;
};

const normalizeQAPairs = (raw: any): QAPair[] => {
  if (!Array.isArray(raw)) return raw as QAPair[];
  return raw.map(normalizeQAPair);
};

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    const requestId = `req-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    (config as any).requestId = requestId;
    const startTime = Date.now();
    (config as any).startTime = startTime;
    
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, {
      requestId,
      method: config.method,
      url: config.url,
      params: config.params,
      data: config.data,
      headers: Object.keys(config.headers || {}),
    });
    
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// Response interceptor for logging
apiClient.interceptors.response.use(
  (response) => {
    const config = response.config as any;
    const requestId = config.requestId || 'unknown';
    const startTime = config.startTime || Date.now();
    const duration = Date.now() - startTime;
    const requestIdHeader = response.headers['x-request-id'] || requestId;
    
    console.log(`[API Response] ${config.method?.toUpperCase()} ${config.url}`, {
      requestId: requestIdHeader,
      status: response.status,
      statusText: response.statusText,
      duration: `${duration}ms`,
      dataSize: JSON.stringify(response.data).length,
      data: response.data,
    });
    
    return response;
  },
  (error) => {
    const config = error.config as any;
    const requestId = config?.requestId || 'unknown';
    const startTime = config?.startTime || Date.now();
    const duration = Date.now() - startTime;
    
    if (error.response) {
      // Server responded with error status
      const requestIdHeader = error.response.headers['x-request-id'] || requestId;
      console.error(`[API Error Response] ${config?.method?.toUpperCase()} ${config?.url}`, {
        requestId: requestIdHeader,
        status: error.response.status,
        statusText: error.response.statusText,
        duration: `${duration}ms`,
        error: error.response.data,
        message: error.response.data?.message || error.message,
      });
    } else if (error.request) {
      // Request made but no response received
      console.error(`[API Network Error] ${config?.method?.toUpperCase()} ${config?.url}`, {
        requestId,
        duration: `${duration}ms`,
        error: 'No response received',
        message: error.message,
      });
    } else {
      // Error setting up request
      console.error('[API Request Setup Error]', {
        requestId,
        error: error.message,
      });
    }
    
    return Promise.reject(error);
  }
);

// Error handler
const handleError = (error: unknown): APIError => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<APIErrorResponse>;
    const errorData = axiosError.response?.data;
    
    // Network error (no response)
    if (!axiosError.response) {
      return new APIError(
        'Network error. Please check your connection.',
        0,
        'Network Error',
        undefined,
        'NETWORK_ERROR'
      );
    }
    
    // API error response
    if (errorData) {
      return new APIError(
        errorData.message || axiosError.message || 'An unexpected error occurred',
        errorData.status_code || axiosError.response.status,
        axiosError.response.statusText,
        errorData.detail,
        errorData.error
      );
    }
    
    // HTTP error without structured response
    return new APIError(
      axiosError.message || 'An unexpected error occurred',
      axiosError.response.status,
      axiosError.response.statusText
    );
  }
  
  if (error instanceof Error) {
    return new APIError(error.message);
  }
  
  return new APIError('An unknown error occurred');
};

// Retry configuration for retryable errors
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second

const retryRequest = async <T>(
  requestFn: () => Promise<T>,
  retries = MAX_RETRIES
): Promise<T> => {
  try {
    return await requestFn();
  } catch (error) {
    const apiError = handleError(error);
    
    if (apiError.isRetryable() && retries > 0) {
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
      return retryRequest(requestFn, retries - 1);
    }
    
    throw apiError;
  }
};

// Session endpoints
export const createSession = async (
  data: CreateSessionRequest
): Promise<QASession> => {
  return retryRequest(async () => {
    const response = await apiClient.post<QASession>('/api/sessions', data);
    return response.data;
  });
};

// Project endpoints
export const listProjects = async (): Promise<Project[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<Project[]>('/api/projects');
    return response.data;
  });
};

export const createProject = async (data: CreateProjectRequest): Promise<Project> => {
  return retryRequest(async () => {
    const response = await apiClient.post<Project>('/api/projects', data);
    return response.data;
  });
};

export const getProject = async (projectId: string): Promise<Project> => {
  return retryRequest(async () => {
    const response = await apiClient.get<Project>(`/api/projects/${projectId}`);
    return response.data;
  });
};

export const getProjectStageOptions = async (
  projectId: string
): Promise<{
  next_actions: Array<{ event: string; to: string; to_label: string }>;
  rollback_targets: string[];
}> => {
  return retryRequest(async () => {
    const response = await apiClient.get(`/api/projects/${projectId}/stage-options`);
    return response.data;
  });
};

export const updateProjectStage = async (
  projectId: string,
  data: UpdateProjectStageRequest
): Promise<Project> => {
  return retryRequest(async () => {
    const response = await apiClient.put<Project>(`/api/projects/${projectId}/stage`, data);
    return response.data;
  });
};

export const uploadProjectDocument = async (
  projectId: string,
  file: File
): Promise<{
  project_id: string;
  document_id: string;
  title: string;
  chunks_created: number;
  errors: string[];
}> => {
  return retryRequest(async () => {
    const form = new FormData();
    form.append('file', file);
    const response = await apiClient.post(`/api/projects/${projectId}/uploads`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  });
};

export const getSession = async (sessionId: string): Promise<QASession> => {
  return retryRequest(async () => {
    const response = await apiClient.get<QASession>(`/api/sessions/${sessionId}`);
    return response.data;
  });
};

export const listSessions = async (
  limit?: number,
  skip?: number
): Promise<QASession[]> => {
  return retryRequest(async () => {
    const params = new URLSearchParams();
    if (limit !== undefined) params.append('limit', limit.toString());
    if (skip !== undefined) params.append('skip', skip.toString());
    const response = await apiClient.get<QASession[]>('/api/sessions', {
      params,
    });
    return response.data;
  });
};

// Question processing endpoints
export const processQuestions = async (
  sessionId: string,
  data: ProcessQuestionsRequest
): Promise<ProcessQuestionsResponse> => {
  console.log('[processQuestions] Starting question processing', {
    sessionId,
    questionCount: data.questions?.length || 0,
    userRole: data.user_role,
    includeHistory: data.include_history,
    questions: data.questions,
  });
  
  return retryRequest(async () => {
    const response = await apiClient.post<ProcessQuestionsResponse>(
      `/api/sessions/${sessionId}/questions`,
      data
    );
    
    const normalized: ProcessQuestionsResponse = {
      ...response.data,
      qa_pairs: normalizeQAPairs((response.data as any).qa_pairs),
    };

    console.log('[processQuestions] Question processing completed', {
      sessionId,
      questionsProcessed: normalized.questions_processed,
      qaPairsCount: normalized.qa_pairs?.length || 0,
      qaPairs: normalized.qa_pairs,
    });
    
    return normalized;
  });
};

export const getQAPairs = async (sessionId: string): Promise<QAPair[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<QAPair[]>(
      `/api/sessions/${sessionId}/qa-pairs`
    );
    return normalizeQAPairs(response.data as any);
  });
};

export const updateAnswer = async (
  qaPairId: string,
  data: UpdateAnswerRequest
): Promise<void> => {
  return retryRequest(async () => {
    await apiClient.put(`/api/qa-pairs/${qaPairId}`, data);
  });
};

export const updateQAPairRating = async (
  qaPairId: string,
  data: UpdateQAPairRatingRequest
): Promise<void> => {
  return retryRequest(async () => {
    await apiClient.put(`/api/qa-pairs/${qaPairId}/rating`, data);
  });
};

export const markSessionOutcome = async (
  sessionId: string,
  outcome: 'successful' | 'unsuccessful'
): Promise<void> => {
  return retryRequest(async () => {
    await apiClient.put(`/api/sessions/${sessionId}/outcome`, { outcome });
  });
};

export const createFollowUpSession = async (
  sessionId: string,
  data: FollowUpSessionRequest
): Promise<QASession> => {
  return retryRequest(async () => {
    const response = await apiClient.post<QASession>(
      `/api/sessions/${sessionId}/follow-up`,
      data
    );
    return response.data;
  });
};

// Export endpoints
export const exportSession = async (
  sessionId: string,
  format: 'markdown' | 'pdf' | 'docx'
): Promise<Blob> => {
  return retryRequest(async () => {
    const response = await apiClient.post(
      `/api/sessions/${sessionId}/export`,
      {},
      {
        params: { format },
        responseType: 'blob',
      }
    );
    return response.data;
  });
};

// =============================================================================
// Document Upload Endpoints
// =============================================================================

/**
 * Upload a document without requiring a project context (standalone upload).
 * The document will be ingested with full tracking and progress reporting.
 *
 * @param file - The file to upload
 * @param projectId - Optional project ID to associate the document with
 * @returns Upload response with document ID, job ID, statistics, and metadata
 */
export const uploadDocument = async (
  file: File,
  projectId?: string
): Promise<DocumentUploadResponse> => {
  return retryRequest(async () => {
    const form = new FormData();
    form.append('file', file);

    const params = new URLSearchParams();
    if (projectId) {
      params.append('project_id', projectId);
    }

    const response = await apiClient.post<DocumentUploadResponse>(
      `/api/documents/upload`,
      form,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        params: projectId ? { project_id: projectId } : undefined,
      }
    );
    return response.data;
  });
};

/**
 * Get a list of all documents with optional filtering and pagination.
 *
 * @param filters - Optional filters (project_id, search)
 * @param limit - Maximum number of documents to return (default 50)
 * @param skip - Number of documents to skip for pagination (default 0)
 * @returns Paginated list of documents
 */
export const getDocuments = async (
  filters?: DocumentFilter,
  limit: number = 50,
  skip: number = 0
): Promise<DocumentListResponse> => {
  return retryRequest(async () => {
    const params: Record<string, string | number> = { limit, skip };

    if (filters?.project_id) {
      params.project_id = filters.project_id;
    }
    if (filters?.search) {
      params.search = filters.search;
    }

    const response = await apiClient.get<DocumentListResponse>('/api/documents', { params });
    return response.data;
  });
};

/**
 * Get a single document by ID.
 *
 * @param documentId - The document ID
 * @returns Document details with metadata and chunk count
 */
export const getDocument = async (documentId: string): Promise<Document> => {
  return retryRequest(async () => {
    const response = await apiClient.get<Document>(`/api/documents/${documentId}`);
    return response.data;
  });
};

/**
 * Delete a document and all its associated chunks.
 *
 * @param documentId - The document ID to delete
 */
export const deleteDocument = async (documentId: string): Promise<void> => {
  return retryRequest(async () => {
    await apiClient.delete(`/api/documents/${documentId}`);
  });
};

// =============================================================================
// Ingestion Job Endpoints
// =============================================================================

/**
 * Get a list of ingestion jobs with optional filtering and pagination.
 *
 * @param filters - Optional filters (status, project_id, filename_contains, date range)
 * @param limit - Maximum number of jobs to return (default 50)
 * @param skip - Number of jobs to skip for pagination (default 0)
 * @returns Paginated list of ingestion jobs
 */
export const getIngestionJobs = async (
  filters?: IngestionJobFilter,
  limit: number = 50,
  skip: number = 0
): Promise<IngestionJobListResponse> => {
  return retryRequest(async () => {
    const params: Record<string, string | number> = { limit, skip };

    if (filters?.status) {
      params.status = filters.status;
    }
    if (filters?.project_id) {
      params.project_id = filters.project_id;
    }
    if (filters?.filename_contains) {
      params.filename_contains = filters.filename_contains;
    }
    if (filters?.created_after) {
      params.created_after = filters.created_after;
    }
    if (filters?.created_before) {
      params.created_before = filters.created_before;
    }

    const response = await apiClient.get<IngestionJobListResponse>('/api/ingestion/jobs', {
      params,
    });
    return response.data;
  });
};

/**
 * Get a single ingestion job by ID.
 *
 * @param jobId - The ingestion job ID
 * @returns Full ingestion job details
 */
export const getIngestionJob = async (jobId: string): Promise<IngestionJob> => {
  return retryRequest(async () => {
    const response = await apiClient.get<IngestionJob>(`/api/ingestion/jobs/${jobId}`);
    return response.data;
  });
};

/**
 * Subscribe to real-time ingestion status updates via Server-Sent Events (SSE).
 * Returns a cleanup function to close the connection.
 *
 * @param jobId - The ingestion job ID to monitor
 * @param onProgress - Callback for progress updates
 * @param onComplete - Callback when job completes (success, partial, or failed)
 * @param onError - Callback for SSE errors
 * @returns Cleanup function to close the EventSource connection
 */
export const subscribeToIngestionStatus = (
  jobId: string,
  onProgress: (progress: IngestionProgress & { status: string }) => void,
  onComplete?: (job: IngestionJob) => void,
  onError?: (error: Event) => void
): (() => void) => {
  const url = `${API_BASE_URL}/api/ingestion/jobs/${jobId}/status`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onProgress(data);

      // Check if job has reached terminal state
      if (data.status === 'success' || data.status === 'partial' || data.status === 'failed') {
        eventSource.close();
        if (onComplete) {
          // Fetch full job details for complete callback
          getIngestionJob(jobId)
            .then(onComplete)
            .catch((err) => {
              console.error('[SSE] Failed to fetch completed job:', err);
            });
        }
      }
    } catch (err) {
      console.error('[SSE] Failed to parse event data:', err);
    }
  };

  eventSource.onerror = (error) => {
    console.error('[SSE] EventSource error:', error);
    eventSource.close();
    if (onError) {
      onError(error);
    }
  };

  // Return cleanup function
  return () => {
    eventSource.close();
  };
};

/**
 * Get aggregate statistics for ingestion jobs.
 *
 * @param projectId - Optional project ID to filter stats
 * @returns Aggregate statistics (total jobs, by status, chunks created, etc.)
 */
export const getIngestionStats = async (projectId?: string): Promise<IngestionStatsResponse> => {
  return retryRequest(async () => {
    const params = projectId ? { project_id: projectId } : undefined;
    const response = await apiClient.get<IngestionStatsResponse>('/api/ingestion/stats', {
      params,
    });
    return response.data;
  });
};

/**
 * Delete an ingestion job record (does not delete the document or chunks).
 *
 * @param jobId - The ingestion job ID to delete
 */
export const deleteIngestionJob = async (jobId: string): Promise<void> => {
  return retryRequest(async () => {
    await apiClient.delete(`/api/ingestion/jobs/${jobId}`);
  });
};

// =============================================================================
// System Health Endpoints
// =============================================================================

/**
 * Check system health including database connectivity and collection status.
 *
 * @returns Health check response with database and collection status
 */
export const getSystemHealth = async (): Promise<HealthCheckResponse> => {
  return retryRequest(async () => {
    const response = await apiClient.get<HealthCheckResponse>('/api/system/health');
    return response.data;
  });
};

/**
 * Get vector search index status and verification results.
 *
 * @returns Index status with configuration and verification results
 */
export const getIndexStatus = async (): Promise<IndexStatusResponse> => {
  return retryRequest(async () => {
    const response = await apiClient.get<IndexStatusResponse>('/api/system/index-status');
    return response.data;
  });
};

/**
 * Verify that a specific document has been indexed and is searchable.
 * Implements retry mechanism for eventual consistency.
 *
 * @param documentId - The document ID to verify
 * @param maxRetries - Maximum retry attempts (default 3)
 * @returns Document verification result
 */
export const verifyDocumentIndexed = async (
  documentId: string,
  maxRetries: number = 3
): Promise<DocumentVerificationResult> => {
  return retryRequest(async () => {
    const response = await apiClient.get<DocumentVerificationResult>(
      `/api/system/verify-document/${documentId}`,
      {
        params: { max_retries: maxRetries },
      }
    );
    return response.data;
  });
};

// =============================================================================
// Tax Office Endpoints
// =============================================================================

/**
 * Search tax offices by name, city, or kodjednostki ID.
 *
 * @param query - Search query string
 * @param limit - Maximum number of results (default 20)
 * @returns List of matching tax offices
 */
export const searchTaxOffices = async (
  query: string,
  limit: number = 20
): Promise<TaxOffice[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<TaxOffice[]>('/api/tax-offices/search', {
      params: { q: query, limit },
    });
    return response.data;
  });
};

/**
 * Get a tax office by its kodjednostki (unique ID).
 *
 * @param kodjednostki - Tax office unique identifier
 * @returns Tax office record
 */
export const getTaxOffice = async (kodjednostki: number): Promise<TaxOffice> => {
  return retryRequest(async () => {
    const response = await apiClient.get<TaxOffice>(`/api/tax-offices/${kodjednostki}`);
    return response.data;
  });
};

/**
 * List all tax offices with pagination.
 *
 * @param limit - Maximum number of results (default 100)
 * @param skip - Number of results to skip for pagination (default 0)
 * @returns List of tax offices
 */
export const listTaxOffices = async (
  limit: number = 100,
  skip: number = 0
): Promise<TaxOffice[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<TaxOffice[]>('/api/tax-offices', {
      params: { limit, skip },
    });
    return response.data;
  });
};

/**
 * Get total count of tax offices.
 *
 * @returns Object with count property
 */
export const getTaxOfficeCount = async (): Promise<{ count: number }> => {
  return retryRequest(async () => {
    const response = await apiClient.get<{ count: number }>('/api/tax-offices/count');
    return response.data;
  });
};

// =============================================================================
// Region Endpoints
// =============================================================================

/**
 * Get all regions (voivodeships).
 *
 * @returns List of regions
 */
export const getRegions = async (): Promise<Region[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<Region[]>('/api/regions');
    return response.data;
  });
};

// =============================================================================
// Industry Endpoints
// =============================================================================

/**
 * Get all industries.
 *
 * @returns List of industries
 */
export const getIndustries = async (): Promise<Industry[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<Industry[]>('/api/industries');
    return response.data;
  });
};

// =============================================================================
// Dashboard Endpoints
// =============================================================================

/**
 * Get dashboard summary statistics.
 *
 * @returns Dashboard summary with project count, session count, success rate, and Q&A quality metrics
 */
export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  return retryRequest(async () => {
    const response = await apiClient.get<DashboardSummary>('/api/dashboard/summary');
    return response.data;
  });
};

/**
 * Get project and session distribution by region.
 *
 * @returns Distribution data for projects and sessions by region
 */
export const getRegionDistribution = async (): Promise<RegionDistribution> => {
  return retryRequest(async () => {
    const response = await apiClient.get<RegionDistribution>('/api/dashboard/distribution/region');
    return response.data;
  });
};

/**
 * Get project distribution by industry.
 *
 * @returns Distribution data for projects by industry
 */
export const getIndustryDistribution = async (): Promise<IndustryDistribution> => {
  return retryRequest(async () => {
    const response = await apiClient.get<IndustryDistribution>('/api/dashboard/distribution/industry');
    return response.data;
  });
};

/**
 * Get project distribution by tax office.
 *
 * @param limit - Maximum number of tax offices to return (default: 20)
 * @returns Distribution data for projects by tax office
 */
export const getTaxOfficeDistribution = async (limit: number = 20): Promise<TaxOfficeDistribution> => {
  return retryRequest(async () => {
    const response = await apiClient.get<TaxOfficeDistribution>('/api/dashboard/distribution/tax-office', {
      params: { limit },
    });
    return response.data;
  });
};

/**
 * Get time-based trends for projects, sessions, and Q&A pairs.
 *
 * @param days - Number of days to look back (default: 30)
 * @param granularity - Time grouping: day, week, or month (default: day)
 * @returns Trend data with time series for each metric
 */
export const getDashboardTrends = async (
  days: number = 30,
  granularity: 'day' | 'week' | 'month' = 'day'
): Promise<TrendsResponse> => {
  return retryRequest(async () => {
    const response = await apiClient.get<TrendsResponse>('/api/dashboard/trends', {
      params: { days, granularity },
    });
    return response.data;
  });
};

/**
 * Get Q&A quality metrics including good/bad ratios.
 *
 * @returns Quality metrics and outcome distribution
 */
export const getQualityMetrics = async (): Promise<QualityMetricsResponse> => {
  return retryRequest(async () => {
    const response = await apiClient.get<QualityMetricsResponse>('/api/dashboard/quality');
    return response.data;
  });
};

