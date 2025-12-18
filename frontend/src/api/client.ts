import axios, { AxiosError } from 'axios';
import type {
  QASession,
  QAPair,
  CreateSessionRequest,
  ProcessQuestionsRequest,
  ProcessQuestionsResponse,
  UpdateAnswerRequest,
  FollowUpSessionRequest,
  APIError,
  APIErrorResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
    
    console.log('[processQuestions] Question processing completed', {
      sessionId,
      questionsProcessed: response.questions_processed,
      qaPairsCount: response.qa_pairs?.length || 0,
      qaPairs: response.qa_pairs,
    });
    
    return response.data;
  });
};

export const getQAPairs = async (sessionId: string): Promise<QAPair[]> => {
  return retryRequest(async () => {
    const response = await apiClient.get<QAPair[]>(
      `/api/sessions/${sessionId}/qa-pairs`
    );
    return response.data;
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

