import type {
  ModelOptionsResponse,
  ProviderName,
  ResearchEvent,
  ResearchJob,
  ResearchMode,
} from "@/lib/types";
import type { ProductErrorCode } from "@/lib/types";

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

export class ApiError extends Error {
  code?: ProductErrorCode;
  retryable: boolean;

  constructor(message: string, code?: ProductErrorCode, retryable = false) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
  }
}

async function responseApiError(response: Response, fallback: string): Promise<ApiError> {
  try {
    const payload = (await response.json()) as {
      detail?: string | { message?: string; code?: ProductErrorCode; retryable?: boolean };
    };
    if (typeof payload.detail === "string") {
      return new ApiError(payload.detail);
    }
    if (payload.detail && typeof payload.detail === "object") {
      return new ApiError(
        payload.detail.message || fallback,
        payload.detail.code,
        Boolean(payload.detail.retryable),
      );
    }
  } catch {
    // 非 JSON 响应不得把服务端原文暴露到产品界面。
  }

  if (response.status === 402) {
    return new ApiError("当前积分不足，无法继续研究。", "insufficient_credits");
  }
  if (response.status === 408 || response.status === 504) {
    return new ApiError("请求未能在规定时间内完成，请重试。", "task_timeout", true);
  }
  if (response.status === 429 || response.status >= 500) {
    return new ApiError("研究服务暂时繁忙，请稍后重试。", "service_unavailable", true);
  }
  return new ApiError(fallback);
}

async function requestJson<T>(
  url: string,
  init: RequestInit | undefined,
  fallback: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError("网络连接不稳定，请检查网络后重试。", "network_error", true);
  }
  if (!response.ok) throw await responseApiError(response, fallback);
  return response.json() as Promise<T>;
}

export async function createResearchJob(input: {
  query: string;
  mode: ResearchMode;
  provider: ProviderName;
  model?: string;
}): Promise<ResearchJob> {
  return requestJson<ResearchJob>(`${API_BASE_URL}/api/research-jobs`, {
    method: "POST",
    headers: visitorHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(input),
  }, "暂时无法创建研究任务，请稍后重试。");
}

export async function getModelOptions(): Promise<ModelOptionsResponse> {
  return requestJson<ModelOptionsResponse>(
    `${API_BASE_URL}/api/models`,
    undefined,
    "暂时无法获取模型列表。",
  );
}

export async function getResearchJob(jobId: string): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}`,
    { headers: visitorHeaders() },
    "暂时无法获取研究任务。",
  );
}

export async function getResearchEvents(jobId: string): Promise<ResearchEvent[]> {
  return requestJson<ResearchEvent[]>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/events`,
    { headers: visitorHeaders() },
    "暂时无法获取研究进度。",
  );
}

export async function cancelResearchJob(jobId: string): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/cancel`,
    { method: "POST", headers: visitorHeaders() },
    "暂时无法停止研究任务。",
  );
}

export async function rerunResearchJob(jobId: string): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/rerun`,
    { method: "POST", headers: visitorHeaders() },
    "暂时无法重新运行研究任务。",
  );
}

export async function retryResearchJob(jobId: string): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/retry`,
    { method: "POST", headers: visitorHeaders() },
    "暂时无法重试研究任务。",
  );
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

export async function exportResearchJobPdf(
  jobId: string,
): Promise<{ blob: Blob; filename: string }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/research-jobs/${jobId}/export/pdf`, {
      headers: visitorHeaders(),
    });
  } catch {
    throw new ApiError("网络连接不稳定，请检查网络后重试。", "network_error", true);
  }
  if (!response.ok) {
    throw await responseApiError(response, "暂时无法导出 PDF。");
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
  return requestJson<ResearchJob[]>(
    `${API_BASE_URL}/api/research-jobs`,
    { headers: visitorHeaders() },
    "暂时无法获取研究历史。",
  );
}

export function createResearchEventSource(jobId: string, afterEventId?: string): EventSource {
  const url = new URL(`${API_BASE_URL}/api/research-jobs/${jobId}/stream`);
  url.searchParams.set("visitor_id", getVisitorId());
  if (afterEventId) {
    url.searchParams.set("after", afterEventId);
  }
  return new EventSource(url);
}
