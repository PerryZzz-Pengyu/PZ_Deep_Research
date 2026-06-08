export type ResearchMode = "quick" | "deep" | "expert";
export type ProviderName = "mock" | "openai" | "anthropic" | "gemini";

export type ResearchJob = {
  id: string;
  query: string;
  mode: ResearchMode;
  provider: string;
  model?: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  final_report?: string | null;
  error?: string | null;
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
  providers: Record<ProviderName, ModelOption[]>;
  defaults: {
    provider: ProviderName;
    openai?: string | null;
    anthropic?: string | null;
    gemini?: string | null;
  };
};
