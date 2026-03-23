export type GenerationStyle =
  | "natural"
  | "news"
  | "drama_movie"
  | "sad"
  | "happy"
  | "charming_attractive";

export type RenderMode = "preview" | "final";
export type CertificationStatus = "pending" | "certifying" | "certified" | "rejected" | "uncertified_legacy";

export type Persona = {
  id: number;
  name: string;
  source_type: string;
  source_ref?: string | null;
  ref_audio_path?: string | null;
  anchor_audio_path?: string | null;
  conditioning_long_path?: string | null;
  speaker_embedding_path?: string | null;
  duration_sec?: number | null;
  transcript?: string | null;
  training_quality?: Record<string, unknown> | null;
  training_status: "idle" | "queued" | "running" | "completed" | "failed";
  training_progress: number;
  training_job_id?: number | null;
  training_error?: string | null;
  training_audio_seconds?: number | null;
  training_source_duration_seconds?: number | null;
  certification_status: CertificationStatus;
  certification_error?: string | null;
  certification_report?: Record<string, unknown> | null;
  render_profile?: Record<string, unknown> | null;
  anchor_candidates?: Array<Record<string, unknown>>;
  certified_profile_version: number;
  created_at: string;
};

export type Job = {
  id: number;
  job_type: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  result_json?: Record<string, unknown> | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
};

export type Generation = {
  id: number;
  persona_id: number;
  input_text: string;
  processed_text: string;
  style: GenerationStyle;
  engine: string;
  render_mode: RenderMode;
  engine_requested?: string | null;
  engine_used?: string | null;
  fallback_engine_used?: string | null;
  segment_count?: number;
  warning_codes?: string[];
  certified_profile_version?: number | null;
  identity_score?: number | null;
  retry_count?: number;
  fallback_applied?: boolean;
  applied_tags?: string[];
  attempts?: Array<Record<string, unknown>>;
  quality_state?: "pass" | "warning" | "hard_fail";
  quality_warnings?: string[];
  llm_enhance_ms?: number | null;
  synthesis_ms?: number | null;
  identity_score_ms?: number | null;
  total_generation_ms?: number | null;
  reasoner_timeout_triggered?: boolean;
  stage_timeout_triggered?: boolean;
  input_chars?: number | null;
  enhanced_chars?: number | null;
  growth_ratio?: number | null;
  disfluency_edits?: string[];
  audio_path?: string | null;
  duration_sec?: number | null;
  status: string;
  created_at: string;
};

export type DeleteGenerationResult = {
  deleted: boolean;
  file_deleted: boolean;
};

export type DeletePersonaResult = {
  deleted: boolean;
  generation_files_deleted: number;
  persona_assets_deleted: boolean;
};
