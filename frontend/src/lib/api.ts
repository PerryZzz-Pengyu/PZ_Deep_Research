import type { ModelOptionsResponse, ProviderName, ResearchJob, ResearchMode } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function createResearchJob(input: {
  query: string;
  mode: ResearchMode;
  provider: ProviderName;
  model?: string;
}): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "创建研究任务失败");
  }

  return response.json();
}

export async function getModelOptions(): Promise<ModelOptionsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/models`);

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "获取模型列表失败");
  }

  return response.json();
}

export function createResearchEventSource(jobId: string): EventSource {
  return new EventSource(`${API_BASE_URL}/api/research-jobs/${jobId}/stream`);
}
