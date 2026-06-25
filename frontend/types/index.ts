export type Severity = "low" | "medium" | "high" | "critical";
export type TicketStatus = "open" | "triaged" | "in_progress" | "resolved" | "closed";
export type TaskStatus = "todo" | "in_progress" | "done";
export type AIReviewStatus = "pending" | "approved" | "overridden";

export interface User {
  id: number;
  name: string;
  email: string;
  role: "requester" | "admin";
  department: string;
  created_at: string;
}

export interface Attachment {
  id: number;
  ticket_id: number;
  file_name: string;
  file_path: string;
  file_type: "screenshot" | "log" | "other";
  mime_type?: string | null;
  size_bytes?: number;
  checksum?: string | null;
  uploaded_at: string;
}

export interface KnowledgeBaseArticle {
  id: number;
  title: string;
  category: string;
  summary: string;
  content: string;
  tags: string[];
  reading_time: number;
  hit_count: number;
  source_name?: string | null;
  source_filename?: string | null;
  source_type?: string;
  source_checksum?: string | null;
  version?: string;
  page_count?: number | null;
  ingestion_run_id?: number | null;
  kb_version?: string;
  updated_at?: string | null;
  ingestion_status?: string;
  index_status?: string;
  created_at: string;
}

export interface TimelineEvent {
  id: number;
  ticket_id: number;
  event_type: string;
  content: string;
  created_at: string;
}

export interface RemediationTask {
  id: number;
  ticket_id: number;
  title: string;
  description: string;
  assigned_to: string;
  status: TaskStatus;
  due_date: string | null;
  created_at: string;
}

export interface AdminNote {
  id: number;
  ticket_id: number;
  author: string;
  content: string;
  created_at: string;
}

export interface AIReview {
  id: number;
  ticket_id: number;
  original_category: string;
  original_severity: Severity;
  corrected_category: string | null;
  corrected_severity: Severity | null;
  run_id?: string | null;
  review_reasons?: string[];
  correction_reason?: string | null;
  reviewer_note: string | null;
  status: AIReviewStatus;
  created_at: string;
  ticket?: Ticket;
}

export interface RetrievedSource {
  id: number;
  article_id: number;
  chunk_id: number;
  chunk_index: number;
  title: string;
  category: string;
  summary: string;
  chunk_summary: string;
  evidence_excerpt: string;
  dense_score: number;
  lexical_score: number;
  fusion_score?: number;
  rerank_score?: number | null;
  final_score: number;
  ranking_stage?: string;
  insufficient?: boolean;
  retrieval_mode: string;
  embedding_provider: string;
  embedding_model?: string | null;
  fallback_reason?: string | null;
  index_version?: string | null;
  corpus_hash?: string | null;
  content_hash?: string;
  article_version?: string;
  kb_version?: string;
  source_filename?: string | null;
  source_type?: string | null;
  page_number?: number | null;
  ingestion_run_id?: number | null;
  evidence_excerpt_snapshot?: string;
  historical_snapshot?: boolean;
}

export interface EvidenceItem {
  id?: string;
  source_type: "text" | "log" | "ocr" | string;
  source_name: string;
  source_id?: string | null;
  excerpt: string;
  signals?: string[];
  signal_tags?: string[];
  available?: boolean;
  redacted?: boolean;
  ocr_status?: string;
  confidence?: number | null;
  error?: string | null;
  metadata?: Record<string, unknown>;
  structured_signals?: Record<string, unknown>;
}

export interface AnalysisStageTrace {
  name: string;
  status: "success" | "degraded" | "failed" | "skipped";
  provider?: string | null;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  input_summary?: string | null;
  output_summary?: string | null;
  error?: string | null;
}

export interface AIAnalysisAudit {
  id: number;
  ticket_id: number;
  run_id: string;
  trace_id: string;
  analysis_version: string;
  provider: string;
  retrieval_mode: string;
  index_version?: string | null;
  corpus_hash?: string | null;
  chunking_config?: Record<string, unknown>;
  stage_traces?: AnalysisStageTrace[];
  final_decision?: Record<string, unknown>;
  resolution?: Record<string, unknown>;
  candidate_sources?: RetrievedSource[];
  previous_diff?: Record<string, unknown>;
  source_chunk_ids: number[];
  evidence: EvidenceItem[];
  retrieved_sources: RetrievedSource[];
  uncertainty: string | null;
  created_at: string;
}

export interface Ticket {
  id: number;
  requester_id: number;
  title: string;
  description: string;
  user_category: string;
  predicted_category: string | null;
  affected_system: string | null;
  urgency: string;
  severity: Severity;
  confidence: number;
  status: TicketStatus;
  assigned_team: string | null;
  suggested_resolution: string | null;
  next_steps: string[];
  related_kb_articles: RetrievedSource[];
  ai_signals: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  requester?: User | null;
  attachment_count?: number;
}

export interface TicketDetail extends Ticket {
  attachments: Attachment[];
  timeline: TimelineEvent[];
  tasks: RemediationTask[];
  admin_notes: AdminNote[];
  ai_review: AIReview | null;
  ai_analysis_audits: AIAnalysisAudit[];
}

export interface AnalyticsSummary {
  total_tickets: number;
  pending_tickets: number;
  high_risk_tickets: number;
  avg_resolution_hours: number;
  today_new_tickets: number;
  ai_review_pending: number;
}
