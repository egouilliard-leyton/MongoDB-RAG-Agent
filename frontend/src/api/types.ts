// Session types
export interface QASession {
  _id: string;
  session_name: string;
  user_role: "junior" | "senior";
  status: "active" | "draft" | "exported" | "approved" | null;
  outcome_status: "pending" | "successful" | "unsuccessful" | null;
  created_at: string;
  updated_at: string;
  metadata?: {
    company_info?: {
      company_name?: string | null;
      industry?: string | null;
      activities?: string | null;
      context?: string | null;
    };
    round_number?: number;
    parent_session_id?: string | null;
  };
}

// Q&A Pair types
export interface Citation {
  document_id: string;
  document_title: string;
  citation_number: number;
  chunk_id?: string;
}

export interface QAPair {
  _id: string;
  session_id: string;
  question: string;
  original_answer: string;
  edited_answer?: string;
  final_answer: string;
  citations: Citation[];
  question_index: number;
  outcome_status: "pending" | "successful" | "unsuccessful";
  created_at: string;
  updated_at: string;
}

// Request/Response types
export interface CreateSessionRequest {
  name: string;
  user_role: "junior" | "senior";
  company_info?: string;
}

export interface ProcessQuestionsRequest {
  questions: string[];
  user_role?: "junior" | "senior";
  include_history?: boolean;
}

export interface ProcessQuestionsResponse {
  qa_pairs: QAPair[];
}

export interface UpdateAnswerRequest {
  edited_answer: string;
}

export interface FollowUpSessionRequest {
  new_questions: string[];
}

// Error types
export type ErrorType = 
  | "network"
  | "validation"
  | "not_found"
  | "conflict"
  | "unauthorized"
  | "server"
  | "unknown";

export interface APIErrorResponse {
  error: string;
  message: string;
  detail?: string;
  status_code: number;
}

export class APIError extends Error {
  public readonly type: ErrorType;
  public readonly status?: number;
  public readonly statusText?: string;
  public readonly detail?: string;
  public readonly errorCode?: string;

  constructor(
    message: string,
    status?: number,
    statusText?: string,
    detail?: string,
    errorCode?: string
  ) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
    this.errorCode = errorCode;
    
    // Determine error type from status code
    if (!status) {
      this.type = "unknown";
    } else if (status >= 500) {
      this.type = "server";
    } else if (status === 401) {
      this.type = "unauthorized";
    } else if (status === 404) {
      this.type = "not_found";
    } else if (status === 409) {
      this.type = "conflict";
    } else if (status >= 400) {
      this.type = "validation";
    } else {
      this.type = "unknown";
    }
  }

  /**
   * Get user-friendly error message
   */
  getUserMessage(): string {
    switch (this.type) {
      case "network":
        return "Network error. Please check your connection and try again.";
      case "validation":
        return this.message || "Invalid input. Please check your data and try again.";
      case "not_found":
        return this.message || "Resource not found.";
      case "conflict":
        return this.message || "Conflict occurred. Please refresh and try again.";
      case "unauthorized":
        return "Unauthorized access. Please check your credentials.";
      case "server":
        return "Server error. Please try again later.";
      default:
        return this.message || "An unexpected error occurred.";
    }
  }

  /**
   * Check if error is retryable
   */
  isRetryable(): boolean {
    return (
      this.type === "network" ||
      (this.type === "server" && this.status && this.status >= 500) ||
      this.status === 503 || // Service Unavailable
      this.status === 429 // Too Many Requests
    );
  }
}

