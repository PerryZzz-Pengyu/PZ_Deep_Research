import type {
  ModelOptionsResponse,
  ProviderName,
  ResearchEvent,
  ResearchJob,
  ResearchMode,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const VISITOR_STORAGE_KEY = "pz-deep-research-visitor-id";

function getVisitorId(): string {
  if (typeof window === "undefined") return "";
  const stored = window.localStorage.getItem(VISITOR_STORAGE_KEY);
  if (stored) return stored;
  const visitorId = window.crypto.randomUUID();
  window.localStorage.setItem(VISITOR_STORAGE_KEY, visitorId);
  return visitorId;
}

function visitorHeaders(headers: HeadersInit = {}): HeadersInit {
  return {
    ...headers,
    "X-PZ-Visitor-ID": getVisitorId(),
  };
}

export async function createResearchJob(input: {
  query: string;
  mode: ResearchMode;
  provider: ProviderName;
  model?: string;
}): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs`, {
    method: "POST",
    headers: visitorHeaders({
      "Content-Type": "application/json",
    }),
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

export async function getResearchJob(jobId: string): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs/${jobId}`, {
    headers: visitorHeaders(),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "获取研究任务失败");
  }
  return response.json();
}

export async function getResearchEvents(jobId: string): Promise<ResearchEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs/${jobId}/events`, {
    headers: visitorHeaders(),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "获取研究事件失败");
  }
  return response.json();
}

export async function cancelResearchJob(jobId: string): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs/${jobId}/cancel`, {
    method: "POST",
    headers: visitorHeaders(),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "取消研究任务失败");
  }
  return response.json();
}

export async function rerunResearchJob(jobId: string): Promise<ResearchJob> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs/${jobId}/rerun`, {
    method: "POST",
    headers: visitorHeaders(),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "重新运行研究任务失败");
  }
  return response.json();
}

function filenameFromContentDisposition(value: string | null, fallback: string) {
  if (!value) return fallback;
  const encodedMatch = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (encodedMatch) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      return fallback;
    }
  }
  const plainMatch = /filename="?([^";]+)"?/i.exec(value);
  return plainMatch?.[1] || fallback;
}

async function responseError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // 非 JSON 错误响应使用统一提示。
  }
  return fallback;
}

export async function exportResearchJobPdf(
  jobId: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs/${jobId}/export/pdf`, {
    headers: visitorHeaders(),
  });
  if (!response.ok) {
    throw new Error(await responseError(response, "导出 PDF 失败"));
  }
  return {
    blob: await response.blob(),
    filename: filenameFromContentDisposition(
      response.headers.get("Content-Disposition"),
      `pz-deep-research-${jobId.slice(0, 8)}.pdf`,
    ),
  };
}

export async function listResearchJobs(): Promise<ResearchJob[]> {
  const response = await fetch(`${API_BASE_URL}/api/research-jobs`, {
    headers: visitorHeaders(),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "获取研究历史失败");
  }
  return response.json();
}

export function createResearchEventSource(jobId: string, afterEventId?: string): EventSource {
  const url = new URL(`${API_BASE_URL}/api/research-jobs/${jobId}/stream`);
  url.searchParams.set("visitor_id", getVisitorId());
  if (afterEventId) {
    url.searchParams.set("after", afterEventId);
  }
  return new EventSource(url);
}
