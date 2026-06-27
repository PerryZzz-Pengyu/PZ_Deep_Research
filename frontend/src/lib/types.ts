export type ResearchMode = "quick" | "deep" | "expert";
export type ResearchDomain = "academic";
export type ProviderName = "mock" | "openai" | "anthropic" | "gemini";
export type ProductErrorCode =
  | "network_error"
  | "service_unavailable"
  | "task_timeout"
  | "source_unavailable"
  | "insufficient_credits"
  | "content_unsupported"
  | "system_error";

export type ResearchJob = {
  id: string;
  rerun_of_job_id?: string | null;
  routing_version?: string | null;
  domain: ResearchDomain;
  query: string;
  mode: ResearchMode;
  provider: string;
  model?: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  draft_report: string;
  final_report?: string | null;
  error?: string | null;
  error_code?: ProductErrorCode | null;
  error_retryable?: boolean;
  error_stage?: string | null;
  created_at: string;
  updated_at: string;
};

export type ResearchEvent = {
  id: string;
  job_id: string;
  type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ModelOption = {
  id: string;
  label: string;
};

export type ModelOptionsResponse = {
  selection_enabled: boolean;
  routing_version: string;
  providers: Record<ProviderName, ModelOption[]>;
  defaults: {
    provider: ProviderName;
    openai?: string | null;
    anthropic?: string | null;
    gemini?: string | null;
  };
};
