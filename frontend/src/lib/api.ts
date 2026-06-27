import type {
  ModelOptionsResponse,
  ProviderName,
  ResearchDomain,
  ResearchEvent,
  ResearchJob,
  ResearchMode,
} from "@/lib/types";
import type { ProductErrorCode } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const VISITOR_STORAGE_KEY = "pz-deep-research-visitor-id";
const EVENT_STREAM_RETRY_DELAYS = [1000, 2000, 5000];

type AuthTokenProvider = () => Promise<string | null>;

let authTokenProvider: AuthTokenProvider | null = null;

export type ResearchCredentials = {
  api_key?: string;
  base_url?: string;
  search_api_key?: string;
  reader_api_key?: string;
};

export function setAuthTokenProvider(provider: AuthTokenProvider | null): void {
  authTokenProvider = provider;
}

function getVisitorId(): string {
  if (typeof window === "undefined") return "";
  const stored = window.localStorage.getItem(VISITOR_STORAGE_KEY);
  if (stored) return stored;
  const visitorId = window.crypto.randomUUID();
  window.localStorage.setItem(VISITOR_STORAGE_KEY, visitorId);
  return visitorId;
}

async function identityHeaders(headers: HeadersInit = {}): Promise<Headers> {
  const result = new Headers(headers);
  result.set("X-PZ-Visitor-ID", getVisitorId());
  const token = await authTokenProvider?.();
  if (token) {
    result.set("Authorization", `Bearer ${token}`);
  }
  return result;
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
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求未能在规定时间内完成，请重试。", "task_timeout", true);
    }
    throw new ApiError("网络连接不稳定，请检查网络后重试。", "network_error", true);
  }
  if (!response.ok) throw await responseApiError(response, fallback);
  return response.json() as Promise<T>;
}

export async function createResearchJob(input: {
  query: string;
  mode: ResearchMode;
  domain?: ResearchDomain;
  provider?: ProviderName;
  model?: string;
} & ResearchCredentials): Promise<ResearchJob> {
  return requestJson<ResearchJob>(`${API_BASE_URL}/api/research-jobs`, {
    method: "POST",
    headers: await identityHeaders({
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

export async function getResearchJob(jobId: string, signal?: AbortSignal): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}`,
    { headers: await identityHeaders(), signal },
    "暂时无法获取研究任务。",
  );
}

export async function getResearchEvents(jobId: string, signal?: AbortSignal): Promise<ResearchEvent[]> {
  return requestJson<ResearchEvent[]>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/events`,
    { headers: await identityHeaders(), signal },
    "暂时无法获取研究进度。",
  );
}

export async function cancelResearchJob(jobId: string): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/cancel`,
    { method: "POST", headers: await identityHeaders() },
    "暂时无法停止研究任务。",
  );
}

export async function rerunResearchJob(
  jobId: string,
  credentials: ResearchCredentials = {},
): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/rerun`,
    {
      method: "POST",
      headers: await identityHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(credentials),
    },
    "暂时无法重新运行研究任务。",
  );
}

export async function retryResearchJob(
  jobId: string,
  credentials: ResearchCredentials = {},
): Promise<ResearchJob> {
  return requestJson<ResearchJob>(
    `${API_BASE_URL}/api/research-jobs/${jobId}/retry`,
    {
      method: "POST",
      headers: await identityHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(credentials),
    },
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
      headers: await identityHeaders(),
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
    { headers: await identityHeaders() },
    "暂时无法获取研究历史。",
  );
}

export const EVENT_STREAM_CLOSED = 2;

export type ResearchEventStream = {
  readyState: number;
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onerror: ((event: Event) => void) | null;
  close: () => void;
};

class AuthenticatedEventStream implements ResearchEventStream {
  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  private readonly abortController = new AbortController();
  private closed = false;
  private lastEventId?: string;

  constructor(
    private readonly jobId: string,
    afterEventId?: string,
  ) {
    this.lastEventId = afterEventId;
    void this.connect();
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.readyState = EVENT_STREAM_CLOSED;
    this.abortController.abort();
  }

  private async connect(): Promise<void> {
    let retryIndex = 0;
    while (!this.closed) {
      this.readyState = 0;
      try {
        const url = new URL(`${API_BASE_URL}/api/research-jobs/${this.jobId}/stream`);
        if (this.lastEventId) {
          url.searchParams.set("after", this.lastEventId);
        }
        const response = await fetch(url, {
          headers: await identityHeaders({ Accept: "text/event-stream" }),
          signal: this.abortController.signal,
          cache: "no-store",
        });
        if (!response.ok || !response.body) {
          throw await responseApiError(response, "研究进度连接失败。");
        }

        this.readyState = 1;
        retryIndex = 0;
        this.onopen?.(new Event("open"));
        await this.readResponse(response);
        if (!this.closed) {
          throw new ApiError("研究进度连接已中断。", "network_error", true);
        }
      } catch (error) {
        if (this.closed || (error instanceof DOMException && error.name === "AbortError")) {
          return;
        }
        this.onerror?.(new Event("error"));
        const retryDelay = EVENT_STREAM_RETRY_DELAYS[
          Math.min(retryIndex, EVENT_STREAM_RETRY_DELAYS.length - 1)
        ];
        retryIndex += 1;
        await new Promise((resolve) => window.setTimeout(resolve, retryDelay));
      }
    }
  }

  private async readResponse(response: Response): Promise<void> {
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (!this.closed) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        this.dispatchBlock(block);
      }
      if (done) break;
    }
    if (buffer.trim()) {
      this.dispatchBlock(buffer);
    }
  }

  private dispatchBlock(block: string): void {
    let eventId = "";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("id:")) {
        eventId = line.slice(3).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
    if (!dataLines.length) return;
    if (eventId) this.lastEventId = eventId;
    this.onmessage?.(
      new MessageEvent("message", {
        data: dataLines.join("\n"),
        lastEventId: eventId,
      }),
    );
  }
}

export function createResearchEventSource(
  jobId: string,
  afterEventId?: string,
): ResearchEventStream {
  return new AuthenticatedEventStream(jobId, afterEventId);
}
