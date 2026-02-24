// Session types
export interface QASession {
  _id: string;
  session_name: string;
  user_role: "junior" | "senior";
  status: "active" | "draft" | "exported" | "approved" | null;
  outcome_status: "pending" | "successful" | "unsuccessful" | null;
  project_id?: string | null;
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
    review_summary?: {
      verdict_counts?: Record<string, number>;
      missing_info?: string[];
      updated_at?: string;
    };
  };
}

// Q&A Pair types
export interface Citation {
  document_id: string;
  document_title: string;
  citation_number: number;
  source?: string;
  similarity?: number;
  chunk_id?: string;
}

export interface QAPair {
  _id: string;
  // Backward-compatibility: some backend payloads may include `qa_pair_id`
  // while `_id` is missing/null. The frontend normalizes this to `_id`.
  qa_pair_id?: string | null;
  session_id: string;
  question: string;
  original_answer: string;
  edited_answer?: string;
  final_answer: string;
  rating_good?: boolean | null;
  rated_at?: string | null;
  rated_by?: string | null;
  was_edited?: boolean;
  edited_at?: string | null;
  review?: {
    verdict: "good" | "needs_info" | "risk";
    summary: string;
    missing_info?: string[];
    confidence?: number;
  } | null;
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
  project_id?: string | null;
  tax_office_id?: number | null;
  region?: string | null;
}

// Project types
export interface ProjectStage {
  key: string;
  updated_at: string;
}

export interface Project {
  _id: string;
  name: string;
  company_info?: Record<string, any>;
  tax_office_id?: number | null;
  region?: string | null;
  industry?: string | null;
  created_at: string;
  updated_at: string;
  stage: ProjectStage;
  stage_history?: Array<{
    at: string;
    from?: string | null;
    to: string;
    event: string;
    note?: string | null;
    by?: string | null;
  }>;
}

export interface CreateProjectRequest {
  name: string;
  tax_office_id?: number | null;
  region?: string | null;
  industry?: string | null;
}

export interface UpdateProjectStageRequest {
  mode: "transition" | "rollback" | "force";
  event: string;
  to_stage: string;
  note?: string | null;
}

export interface ProcessQuestionsRequest {
  questions: string[];
  user_role?: "junior" | "senior";
  include_history?: boolean;
}

export interface ProcessQuestionsResponse {
  questions_processed: number;
  qa_pairs: QAPair[];
}

export interface UpdateAnswerRequest {
  edited_answer: string;
}

export interface UpdateQAPairRatingRequest {
  rating_good: boolean | null;
}

export interface FollowUpSessionRequest {
  new_questions: string[];
}

// =============================================================================
// Ingestion Types
// =============================================================================

/**
 * Stages in the document ingestion pipeline.
 */
export type IngestionStage =
  | "uploading"
  | "converting"
  | "extracting_metadata"
  | "chunking"
  | "embedding"
  | "storing"
  | "verifying"
  | "complete"
  | "failed";

/**
 * Status of an ingestion job.
 */
export type IngestionStatus =
  | "pending"
  | "in_progress"
  | "success"
  | "partial"
  | "failed";

/**
 * Statistics collected during document ingestion.
 */
export interface IngestionStatistics {
  chunks_created: number;
  total_tokens: number;
  avg_chunk_tokens: number;
  sections_found: number;
  sections_expected: number;
  file_size_bytes: number;
  processing_time_ms: number;
}

/**
 * Real-time progress update for an ingestion job.
 */
export interface IngestionProgress {
  stage: IngestionStage;
  progress_pct: number;
  message: string;
  timestamp: string;
}

/**
 * Complete ingestion job record.
 */
export interface IngestionJob {
  _id: string;
  document_id: string | null;
  project_id: string | null;
  filename: string;
  file_size_bytes: number;
  content_type: string | null;
  status: IngestionStatus;
  current_stage: IngestionStage;
  progress_pct: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  statistics: IngestionStatistics;
  metadata_extracted: Record<string, any>;
  warnings: string[];
  errors: string[];
  progress_history?: IngestionProgress[];
}

/**
 * Response model for paginated ingestion job list.
 */
export interface IngestionJobListResponse {
  jobs: IngestionJob[];
  total: number;
  limit: number;
  skip: number;
  has_more: boolean;
}

/**
 * Aggregate statistics for ingestion jobs.
 */
export interface IngestionAggregateStats {
  total_jobs: number;
  by_status: Record<string, number>;
  total_chunks_created: number;
  total_tokens_processed: number;
  avg_duration_ms: number;
}

/**
 * Response model for ingestion statistics endpoint.
 */
export interface IngestionStatsResponse {
  stats: IngestionAggregateStats;
  project_id: string | null;
}

/**
 * Filter options for listing ingestion jobs.
 */
export interface IngestionJobFilter {
  status?: IngestionStatus;
  project_id?: string;
  filename_contains?: string;
  created_after?: string;
  created_before?: string;
}

// =============================================================================
// Document Types
// =============================================================================

/**
 * Document metadata extracted during ingestion.
 */
export interface DocumentMetadata {
  file_path?: string;
  file_size?: number;
  word_count?: number;
  line_count?: number;
  section_count?: number;
  document_type?: string;
  document_date?: string;
  id_informacji?: string;
  sygnatura?: string;
  interpretation_stance?: string;
  outcome_status?: string;
  ingestion_date?: string;
  project_id?: string;
  [key: string]: any;
}

/**
 * Response model for a single document.
 */
export interface Document {
  _id: string;
  title: string;
  source: string;
  metadata: DocumentMetadata;
  project_id: string | null;
  created_at: string;
  chunk_count: number;
}

/**
 * Response model for paginated document list.
 */
export interface DocumentListResponse {
  documents: Document[];
  total: number;
  limit: number;
  skip: number;
  has_more: boolean;
}

/**
 * Response model for document upload.
 */
export interface DocumentUploadResponse {
  document_id: string | null;
  job_id: string;
  title: string;
  filename: string;
  status: string;
  chunks_created: number;
  total_tokens: number;
  metadata_extracted: Record<string, any>;
  warnings: string[];
  errors: string[];
  processing_time_ms: number;
}

/**
 * Filter options for listing documents.
 */
export interface DocumentFilter {
  project_id?: string;
  search?: string;
}

// =============================================================================
// System/Health Types
// =============================================================================

/**
 * Status of a database collection.
 */
export interface CollectionStatus {
  name: string;
  exists: boolean;
  document_count: number;
  error?: string;
}

/**
 * Database connectivity status.
 */
export interface DatabaseStatus {
  connected: boolean;
  latency_ms: number | null;
  database_name: string;
  error?: string;
}

/**
 * Vector/text search index information.
 */
export interface IndexInfo {
  name: string;
  type: string;
  status: string;
  field?: string;
  dimensions?: number;
  similarity?: string;
  error?: string;
}

/**
 * Result of index verification test.
 */
export interface IndexVerificationResult {
  searched: boolean;
  results_found: number;
  sample_result?: Record<string, any>;
  error?: string;
}

/**
 * Response model for system health check.
 */
export interface HealthCheckResponse {
  status: "healthy" | "degraded" | "unhealthy";
  database: DatabaseStatus;
  collections: CollectionStatus[];
  timestamp: string;
}

/**
 * Response model for vector index status.
 */
export interface IndexStatusResponse {
  vector_index: IndexInfo;
  text_index?: IndexInfo;
  verification: IndexVerificationResult;
  recommendations: string[];
}

/**
 * Document verification result.
 */
export interface DocumentVerificationResult {
  document_id: string;
  exists: boolean;
  indexed: boolean;
  chunks_in_database: number;
  chunks_searchable: number;
  retry_attempts: number;
  error?: string;
}

// =============================================================================
// Error Types
// =============================================================================

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

// =============================================================================
// Reference Data Types
// =============================================================================

/**
 * Tax Office (Urząd Skarbowy) model.
 * Represents one of 590 Polish tax offices with complete contact information.
 */
export interface TaxOffice {
  _id?: string;
  kodjednostki: number;
  nazwa_urzedu: string;
  typ: string;
  wojewodztwo: string;
  miasto: string;
  ulica: string;
  nr_budynku: string;
  kod_pocztowy: string;
  telefon: string;
  email: string;
  adres_bip: string;
}

/**
 * Region (Voivodeship) model.
 * Represents one of 16 Polish voivodeships.
 */
export interface Region {
  _id?: string;
  name: string;
  display_name: string;
}

/**
 * Industry classification model.
 * Represents one of 19 predefined industry categories.
 */
export interface Industry {
  _id?: string;
  name_polish: string;
  name_english: string;
  code: string;
}

// =============================================================================
// Dashboard Types
// =============================================================================

/**
 * Dashboard summary metrics.
 */
export interface DashboardSummary {
  project_count: number;
  session_count: number;
  qa_pair_count: number;
  success_rate: number;
  qa_quality: {
    total: number;
    rated: number;
    unrated: number;
    good: number;
    bad: number;
    good_ratio: number;
    exemplar_count: number;
  };
  timestamp: string;
}

/**
 * Distribution data point for charts.
 */
export interface DistributionItem {
  name: string;
  count: number;
  label?: string;
}

/**
 * Tax office distribution item with additional details.
 */
export interface TaxOfficeDistributionItem {
  tax_office_id: number;
  nazwa_urzedu: string;
  miasto: string;
  count: number;
}

/**
 * Region distribution response.
 */
export interface RegionDistribution {
  projects: DistributionItem[];
  sessions: DistributionItem[];
}

/**
 * Industry distribution response.
 */
export interface IndustryDistribution {
  industries: DistributionItem[];
}

/**
 * Tax office distribution response.
 */
export interface TaxOfficeDistribution {
  tax_offices: TaxOfficeDistributionItem[];
}

/**
 * Time series trend data point.
 */
export interface TrendDataPoint {
  date: string;
  count: number;
}

/**
 * Trends response from API.
 */
export interface TrendsResponse {
  period_days: number;
  granularity: 'day' | 'week' | 'month';
  start_date: string;
  projects: TrendDataPoint[];
  sessions: TrendDataPoint[];
  qa_pairs: TrendDataPoint[];
}

/**
 * Quality metrics response from API.
 */
export interface QualityMetricsResponse {
  quality_metrics: {
    total: number;
    rated: number;
    unrated: number;
    good: number;
    bad: number;
    good_ratio: number;
    exemplar_count: number;
  };
  outcome_distribution: DistributionItem[];
}

// =============================================================================
// Settings Types
// =============================================================================

export interface SearchParamsOverride {
  match_count: number | null;
  rrf_k: number | null;
  qa_history_match_count: number | null;
}

export interface StageDefaultConfig {
  system_prompt_append: string | null;
  search_params: SearchParamsOverride;
}

export interface GlobalSettings {
  main_system_prompt: string;
  follow_up_context_prompt: string;
  qa_history_prompt: string;
  stage_defaults: StageDefaultConfig;
  default_match_count: number;
  max_match_count: number;
  enable_question_decomposition: boolean;
  enable_iterative_refinement: boolean;
  enable_qa_history_search: boolean;
  rrf_k_constant: number;
  qa_history_match_count: number;
  llm_model: string;
  llm_base_url: string;
  embedding_model: string;
  show_full_citations: boolean;
}

export interface SettingsResponse extends GlobalSettings {
  id: string;
  version: number;
  updated_at: string; // ISO 8601
}

export interface SettingsUpdateRequest {
  main_system_prompt?: string;
  follow_up_context_prompt?: string;
  qa_history_prompt?: string;
  stage_defaults?: Partial<StageDefaultConfig>;
  default_match_count?: number;
  max_match_count?: number;
  enable_question_decomposition?: boolean;
  enable_iterative_refinement?: boolean;
  enable_qa_history_search?: boolean;
  rrf_k_constant?: number;
  qa_history_match_count?: number;
  llm_model?: string;
  llm_base_url?: string;
  embedding_model?: string;
  show_full_citations?: boolean;
}

export interface SettingsVersion {
  version: number;
  changed_fields: string[];
  summary: string;
  created_at: string; // ISO 8601
}

export interface ParameterSuggestion {
  suggestion_id: string;
  parameter: string;
  current_value: number | string | boolean;
  suggested_value: number | string | boolean;
  confidence: number; // 0.0 - 1.0
  rationale: string;
}

export interface PromptTestRequest {
  prompt: string;
  test_question: string;
}

export interface PromptTestResponse {
  answer: string;
  latency_ms: number;
}

// =============================================================================
// Workflow Types
// =============================================================================

export interface MetadataFieldDef {
  key: string;
  label: string;
  field_type: "text" | "number" | "date" | "select";
  required: boolean;
  options: string[] | null; // for "select" type
}

export interface TransitionCondition {
  type: string; // e.g. "all_questions_answered", "min_rating"
  params?: Record<string, unknown>;
}

export interface StageConfig {
  system_prompt_append: string | null;
  search_params: SearchParamsOverride;
  metadata_fields: MetadataFieldDef[];
  auto_advance: boolean;
}

export interface StageTransition {
  to_stage_id: string;
  label: string;
  condition: TransitionCondition | null;
}

export interface WorkflowStage {
  id: string;
  label: string;
  description: string;
  order: number;
  color: string; // hex
  config: StageConfig;
  transitions: StageTransition[];
}

export type WorkflowType = "project" | "qa_session" | "qa_pair" | "agentic";

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  workflow_type: WorkflowType;
  stages: WorkflowStage[];
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface WorkflowListItem {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  workflow_type: WorkflowType;
  stage_count: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreateRequest {
  name: string;
  description?: string;
  is_default?: boolean;
  workflow_type?: WorkflowType;
  stages: WorkflowStage[];
}

// =============================================================================
// Dashboard Extended Types (Settings/Workflow features)
// =============================================================================

export interface StageFunnelItem {
  stage_id: string;
  label: string;
  color: string;
  count: number;
  percentage: number;
}

export interface StageFunnelResponse {
  funnel: StageFunnelItem[];
  total_projects: number;
}

export interface QualityTrendPoint {
  date: string;
  good_count: number;
  bad_count: number;
  total_rated: number;
  good_ratio: number;
}

export interface QualityTrendResponse {
  trend: QualityTrendPoint[];
  period_days: number;
  granularity: "day" | "week" | "month";
}

export interface KBHealthData {
  total_documents: number;
  total_chunks: number;
  avg_chunks_per_doc: number;
  embedding_coverage: number; // 0.0 - 1.0
  last_ingestion: string | null;
  stale_document_count: number;
  stale_threshold_days: number;
}

export interface SystemMetricsData {
  avg_response_time_ms: number;
  avg_search_time_ms: number;
  total_queries_24h: number;
  total_queries_7d: number;
  error_rate_24h: number;
  uptime_seconds: number;
}

