"use client";

import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  PauseCircle,
  Search,
  Settings2,
  Sparkles,
  Square,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

import {
  cancelResearchJob,
  createResearchEventSource,
  createResearchJob,
  getModelOptions,
  getResearchEvents,
  getResearchJob,
} from "@/lib/api";
import type { ModelOption, ProviderName, ResearchEvent, ResearchJob, ResearchMode } from "@/lib/types";

const ACTIVE_JOB_STORAGE_KEY = "pz-deep-research-active-job";

const modes: Array<{ value: ResearchMode; label: string; detail: string }> = [
  { value: "quick", label: "快速", detail: "3源短文" },
  { value: "deep", label: "深度", detail: "10源综述" },
  { value: "expert", label: "专家", detail: "20源论文" },
];

const providers: Array<{ value: ProviderName; label: string }> = [
  { value: "mock", label: "开发模式" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Claude" },
  { value: "gemini", label: "Gemini" },
];

const fallbackModelOptions: Record<ProviderName, ModelOption[]> = {
  mock: [{ id: "", label: "开发模式" }],
  openai: [
    { id: "gpt-5.4-mini", label: "gpt-5.4-mini" },
    { id: "gpt-5.5", label: "gpt-5.5" },
    { id: "gpt-5.4", label: "gpt-5.4" },
    { id: "gpt-5.4-nano", label: "gpt-5.4-nano" },
    { id: "gpt-5-mini", label: "gpt-5-mini" },
    { id: "gpt-5-nano", label: "gpt-5-nano" },
  ],
  anthropic: [{ id: "claude-sonnet-4-6", label: "claude-sonnet-4-6" }],
  gemini: [{ id: "gemini-2.5-flash", label: "gemini-2.5-flash" }],
};

type SourceItem = {
  citationId: string;
  searchId?: string;
  sourceKind?: string;
  title: string;
  url: string;
  snippet?: string;
  query?: string;
  readStatus?: string;
  evidenceLevel?: string;
  evidenceNote?: string;
  contentPreview?: string;
};

function getEventIcon(type: string) {
  if (type === "completed") return <CheckCircle2 size={16} />;
  if (type === "cancelled") return <Square size={15} />;
  if (type.startsWith("tool")) return <Search size={16} />;
  if (type.startsWith("llm")) return <Bot size={16} />;
  return <Sparkles size={16} />;
}

function isProviderName(value: string): value is ProviderName {
  return providers.some((item) => item.value === value);
}

function mergeEvent(current: ResearchEvent[], nextEvent: ResearchEvent) {
  if (current.some((event) => event.id === nextEvent.id)) return current;
  return [...current, nextEvent];
}

function jobStatusLabel(status: ResearchJob["status"] | "") {
  if (status === "queued") return "等待开始";
  if (status === "running") return "研究中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已取消";
  return "尚未创建";
}

function parseSources(rawSources: unknown): SourceItem[] {
  if (!Array.isArray(rawSources)) return [];
  return rawSources.flatMap((source, index) => {
    if (!source || typeof source !== "object") return [];
    const maybeSource = source as {
      citation_id?: unknown;
      search_id?: unknown;
      source_kind?: unknown;
      title?: unknown;
      url?: unknown;
      snippet?: unknown;
      query?: unknown;
      read_status?: unknown;
      evidence_level?: unknown;
      evidence_note?: unknown;
      content_preview?: unknown;
    };
    if (typeof maybeSource.url !== "string") return [];
    return [
      {
        citationId:
          typeof maybeSource.citation_id === "string"
            ? maybeSource.citation_id
            : typeof maybeSource.search_id === "string"
              ? maybeSource.search_id
              : String(index + 1),
        searchId: typeof maybeSource.search_id === "string" ? maybeSource.search_id : undefined,
        sourceKind: typeof maybeSource.source_kind === "string" ? maybeSource.source_kind : undefined,
        title: typeof maybeSource.title === "string" ? maybeSource.title : maybeSource.url,
        url: maybeSource.url,
        snippet: typeof maybeSource.snippet === "string" ? maybeSource.snippet : undefined,
        query: typeof maybeSource.query === "string" ? maybeSource.query : undefined,
        readStatus: typeof maybeSource.read_status === "string" ? maybeSource.read_status : undefined,
        evidenceLevel: typeof maybeSource.evidence_level === "string" ? maybeSource.evidence_level : undefined,
        evidenceNote: typeof maybeSource.evidence_note === "string" ? maybeSource.evidence_note : undefined,
        contentPreview: typeof maybeSource.content_preview === "string" ? maybeSource.content_preview : undefined,
      },
    ];
  });
}

function isVisitedSource(source: SourceItem) {
  if (source.sourceKind === "visited_source") return true;
  return /^\d+$/.test(source.citationId) && source.readStatus !== "search_result";
}

function faviconUrl(url: string) {
  try {
    const hostname = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${hostname}&sz=32`;
  } catch {
    return "";
  }
}

function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function formatApaReference(source: SourceItem) {
  return `${source.title}. (n.d.). Retrieved from ${source.url}`;
}

function evidenceLabel(source: SourceItem) {
  const value = source.evidenceLevel || source.readStatus;
  if (value === "full_text") return "全文证据";
  if (value === "partial_text") return "部分正文";
  if (value === "metadata_only") return "访问受限";
  if (value === "metadata") return "题录摘要";
  if (value === "mock") return "开发占位";
  if (value === "unavailable") return "不可用";
  return value || "未分级";
}

function evidenceClass(source: SourceItem) {
  const value = source.evidenceLevel || source.readStatus;
  if (value === "full_text") return "strong";
  if (value === "partial_text") return "medium";
  if (value === "metadata" || value === "metadata_only") return "limited";
  return "muted";
}

function markdownWithCitationLinks(report: string, sourceByCitation: Map<string, SourceItem>) {
  return report.replace(/\[(\d+)\](?!\()/g, (match, citationId: string) => {
    const source = sourceByCitation.get(citationId);
    return source ? `[[${citationId}]](${source.url})` : match;
  });
}

function nodeText(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  return "";
}

function markdownComponents(sourceByCitation: Map<string, SourceItem>): Components {
  return {
    a({ href, children }) {
      const text = nodeText(children);
      const match = /^\[(\d+)\]$/.exec(text);
      if (match) {
        const source = sourceByCitation.get(match[1]);
        return (
          <span className="citation-wrap">
            <sup className="citation-mark">{text}</sup>
            {source ? (
              <span className="citation-popover" role="tooltip">
                <span className="source-topline">
                  <span
                    className="source-favicon"
                    style={faviconUrl(source.url) ? { backgroundImage: `url(${faviconUrl(source.url)})` } : undefined}
                  />
                  <span className="source-citation">[{source.citationId}]</span>
                  <span className="source-domain">{hostname(source.url)}</span>
                </span>
                <strong>{source.title}</strong>
                <span className={`evidence-badge ${evidenceClass(source)}`}>{evidenceLabel(source)}</span>
                {source.evidenceNote ? <small>{source.evidenceNote}</small> : null}
                <span className="source-url">{source.url}</span>
              </span>
            ) : null}
          </span>
        );
      }
      return (
        <a href={href} rel="noreferrer" target="_blank">
          {children}
        </a>
      );
    },
  };
}

function SourceCard({ source }: { source: SourceItem }) {
  const icon = faviconUrl(source.url);
  return (
    <a className="source-card" href={source.url} rel="noreferrer" target="_blank">
      <div className="source-topline">
        <span className="source-favicon" style={icon ? { backgroundImage: `url(${icon})` } : undefined} />
        <span className="source-citation">[{source.citationId}]</span>
        <span className="source-domain">{hostname(source.url)}</span>
        <span className={`evidence-badge ${evidenceClass(source)}`}>{evidenceLabel(source)}</span>
        <ExternalLink size={13} />
      </div>
      <strong>{source.title}</strong>
      {source.snippet ? <small>{source.snippet}</small> : null}
      {source.evidenceNote ? <small>{source.evidenceNote}</small> : null}
      <span className="source-url">{source.url}</span>
    </a>
  );
}

function ToolOutput({ content }: { content: string }) {
  return (
    <details className="tool-output">
      <summary>查看工具返回</summary>
      <pre>{content}</pre>
    </details>
  );
}

function EventDetail({ event }: { event: ResearchEvent }) {
  if (event.type === "tool_result") {
    const eventSources = parseSources(event.payload.sources);
    const content = event.payload.content;
    return (
      <>
        {typeof content === "string" && content ? <ToolOutput content={content} /> : null}
        {eventSources.length ? (
          <div className="event-source-grid">
            {eventSources.map((source) => (
              <SourceCard key={`${event.id}-${source.citationId}-${source.url}`} source={source} />
            ))}
          </div>
        ) : null}
      </>
    );
  }

  if (event.type === "evidence_required") {
    const missing = event.payload.missing;
    return Array.isArray(missing) ? <p className="event-note">补充步骤：{missing.join("、")}</p> : null;
  }

  if (event.type === "visit_progress") {
    const visited = event.payload.visited;
    const fullText = event.payload.full_text;
    const target = event.payload.target;
    if (typeof visited === "number" && typeof target === "number") {
      return (
        <p className="event-note">
          已访问 {visited} 个候选来源
          {typeof fullText === "number" ? `，全文证据 ${fullText}/${target} 个` : ""}
        </p>
      );
    }
    return null;
  }

  if (event.type === "evidence_ready") {
    const total = event.payload.total_cards;
    return typeof total === "number" ? <p className="event-note">已抽取证据卡片 {total} 张</p> : null;
  }

  if (event.type === "source_selected") {
    const total = event.payload.total_available;
    const selected = event.payload.selected_count;
    const target = event.payload.target;
    const fullText = event.payload.full_text_count;
    const degraded = event.payload.degraded === true;
    const shortfall = event.payload.full_text_shortfall === true;
    const notes: string[] = [];
    if (degraded) notes.push("来源数量不足目标，已降级处理");
    if (shortfall) notes.push("全文证据不足，部分结论基于摘要/受限来源");
    return (
      <p className="event-note">
        已筛选来源：最终 {typeof selected === "number" ? selected : "?"}
        {typeof target === "number" ? `/${target}` : ""} 个
        {typeof fullText === "number" ? `，全文证据 ${fullText} 个` : ""}
        {typeof total === "number" ? `（共访问 ${total} 个候选）` : ""}
        {notes.length ? `（${notes.join("；")}）` : ""}
      </p>
    );
  }

  if (event.type === "citation_required") {
    const missing = event.payload.missing;
    return Array.isArray(missing) ? <p className="event-note">需要重写：{missing.join("、")}</p> : null;
  }

  if (event.type === "protocol_warning") {
    const expectedTool = event.payload.expected_tool;
    const actualTool = event.payload.actual_tool;
    const toolCallCount = event.payload.tool_call_count;
    if (typeof expectedTool === "string") {
      return <p className="event-note">流程纠偏：当前需要 {expectedTool}，模型返回了 {String(actualTool || "其他输出")}。</p>;
    }
    if (typeof toolCallCount === "number") {
      return <p className="event-note">流程纠偏：模型一次返回 {toolCallCount} 个工具调用，本轮只执行第一个。</p>;
    }
  }

  if (event.type === "llm_result") {
    const preview = event.payload.content_preview;
    return typeof preview === "string" && preview ? <p className="event-note">{preview}</p> : null;
  }

  return null;
}

export function ResearchWorkspace() {
  const [query, setQuery] = useState("对比 Claude、ChatGPT 和 Gemini 做深度研究产品时各自的优势与风险");
  const [mode, setMode] = useState<ResearchMode>("deep");
  const [provider, setProvider] = useState<ProviderName>("mock");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState(fallbackModelOptions);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [report, setReport] = useState("");
  const [liveModelText, setLiveModelText] = useState("");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState<ResearchJob["status"] | "">("");
  const [isRunning, setIsRunning] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);

  const sources = useMemo(() => {
    let selected: SourceItem[] = [];
    for (const event of events) {
      if (event.type !== "source_selected" && event.type !== "completed") continue;
      const seen = new Set<string>();
      const eventSources: SourceItem[] = [];
      for (const source of parseSources(event.payload.sources)) {
        if (!isVisitedSource(source)) continue;
        if (seen.has(source.url)) continue;
        seen.add(source.url);
        eventSources.push(source);
      }
      if (eventSources.length) selected = eventSources;
    }
    return selected;
  }, [events]);

  const sourceByCitation = useMemo(() => {
    return new Map(sources.map((source) => [source.citationId, source]));
  }, [sources]);
  const reportMarkdown = useMemo(() => markdownWithCitationLinks(report, sourceByCitation), [report, sourceByCitation]);
  const reportMarkdownComponents = useMemo(() => markdownComponents(sourceByCitation), [sourceByCitation]);

  const currentModelOptions = modelOptions[provider] ?? fallbackModelOptions[provider];
  const selectedModel = currentModelOptions.some((item) => item.id === model)
    ? model
    : currentModelOptions[0]?.id ?? "";

  const connectToJob = useCallback((targetJobId: string, afterEventId?: string) => {
    eventSourceRef.current?.close();
    const eventSource = createResearchEventSource(targetJobId, afterEventId);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setError((current) => (current.startsWith("事件流连接中断") ? "" : current));
    };

    eventSource.onmessage = (message) => {
      const nextEvent = JSON.parse(message.data) as ResearchEvent;
      if (nextEvent.type === "job_snapshot") {
        const status = nextEvent.payload.status;
        const finalReport = nextEvent.payload.final_report;
        const draftReport = nextEvent.payload.draft_report;
        if (typeof finalReport === "string" && finalReport) {
          setReport(finalReport);
        } else if (typeof draftReport === "string") {
          setReport(draftReport);
        }
        if (
          status === "queued" ||
          status === "running" ||
          status === "completed" ||
          status === "failed" ||
          status === "cancelled"
        ) {
          setJobStatus(status);
          setIsRunning(status === "queued" || status === "running");
          if (status === "failed" && typeof nextEvent.payload.error === "string") {
            setError(nextEvent.payload.error);
          }
        }
        return;
      }
      if (nextEvent.type === "llm_delta") {
        const delta = nextEvent.payload.delta;
        if (typeof delta === "string") {
          setLiveModelText((current) => current + delta);
        }
        return;
      }
      if (nextEvent.type === "report_delta") {
        const delta = nextEvent.payload.delta;
        const draftReport = nextEvent.payload.draft_report;
        if (typeof draftReport === "string") {
          setReport(draftReport);
        } else if (typeof delta === "string") {
          setReport((current) => current + delta);
        }
        return;
      }
      if (nextEvent.type === "report_reset") {
        setReport("");
        setEvents((current) => mergeEvent(current, nextEvent));
        return;
      }

      setEvents((current) => mergeEvent(current, nextEvent));
      if (nextEvent.type === "llm_start") {
        setLiveModelText("");
      }
      if (nextEvent.type === "completed") {
        const finalReport = nextEvent.payload.final_report;
        if (typeof finalReport === "string") {
          setReport(finalReport);
        }
        setJobStatus("completed");
        setIsRunning(false);
        eventSource.close();
        if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
      }
      if (nextEvent.type === "failed") {
        setError(nextEvent.message);
        setJobStatus("failed");
        setIsRunning(false);
        eventSource.close();
        if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
      }
      if (nextEvent.type === "cancelled") {
        setJobStatus("cancelled");
        setIsRunning(false);
        setIsCancelling(false);
        eventSource.close();
        if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
      }
    };

    eventSource.onerror = () => {
      if (eventSource.readyState !== EventSource.CLOSED) {
        setError("事件流连接中断，正在自动重连...");
        return;
      }
      setError("事件流连接已关闭，请刷新页面恢复任务");
      setIsRunning(false);
      if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
    };
  }, []);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    getModelOptions()
      .then((payload) => {
        if (ignore) return;
        setModelOptions({ ...fallbackModelOptions, ...payload.providers });
        const defaultProvider = payload.defaults.provider;
        if (!window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY) && isProviderName(defaultProvider)) {
          setProvider(defaultProvider);
        }
      })
      .catch(() => {
        // 保留本地兜底列表即可，界面仍然可用。
      });

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    const storedJobId = window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
    if (!storedJobId) {
      const timer = window.setTimeout(() => {
        if (!ignore) setIsRestoring(false);
      }, 0);
      return () => {
        ignore = true;
        window.clearTimeout(timer);
      };
    }

    Promise.all([getResearchJob(storedJobId), getResearchEvents(storedJobId)])
      .then(([job, restoredEvents]) => {
        if (ignore) return;
        setJobId(job.id);
        setJobStatus(job.status);
        setQuery(job.query);
        setMode(job.mode);
        if (isProviderName(job.provider)) setProvider(job.provider);
        setModel(job.model || "");
        setEvents(restoredEvents);
        setReport(job.final_report || job.draft_report || "");
        setLiveModelText("");
        setError(job.error || "");

        const shouldResume = job.status === "queued" || job.status === "running";
        setIsRunning(shouldResume);
        if (shouldResume) {
          connectToJob(job.id, restoredEvents.at(-1)?.id);
        }
      })
      .catch(() => {
        if (ignore) return;
        window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
        setJobId("");
        setJobStatus("");
      })
      .finally(() => {
        if (!ignore) setIsRestoring(false);
      });

    return () => {
      ignore = true;
    };
  }, [connectToJob]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || isRunning || isRestoring) return;

    setError("");
    setEvents([]);
    setReport("");
    setLiveModelText("");
    setIsRunning(true);
    setJobStatus("queued");

    try {
      const job = await createResearchJob({ query, mode, provider, model: selectedModel || undefined });
      setJobId(job.id);
      setJobStatus(job.status);
      window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, job.id);
      connectToJob(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建研究任务失败");
      setIsRunning(false);
      setJobStatus("failed");
    }
  }

  async function handleCancel() {
    if (!jobId || !isRunning || isCancelling) return;
    setIsCancelling(true);
    setError("");
    try {
      const cancelledJob = await cancelResearchJob(jobId);
      const restoredEvents = await getResearchEvents(jobId);
      setEvents(restoredEvents);
      setReport(cancelledJob.final_report || cancelledJob.draft_report || "");
      setJobStatus("cancelled");
      setIsRunning(false);
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消研究任务失败");
    } finally {
      setIsCancelling(false);
    }
  }

  return (
    <main className="workspace-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">PZ</div>
          <div>
            <strong>PZ Deep Research</strong>
            <span>研究工作台</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="主导航">
          <button className="nav-item active" type="button">
            <Search size={16} />
            研究
          </button>
          <button className="nav-item" type="button">
            <FileText size={16} />
            历史
          </button>
          <button className="nav-item" type="button">
            <Settings2 size={16} />
            设置
          </button>
        </nav>

        <div className="sidebar-block">
          <span className="block-label">当前任务</span>
          <strong className="job-id-text">{jobId || "尚未创建"}</strong>
          <span className={`job-status ${jobStatus || "idle"}`}>{jobStatusLabel(jobStatus)}</span>
        </div>
      </aside>

      <section className="main-panel">
        <form className="research-form" onSubmit={handleSubmit}>
          <div className="field-row">
            <label htmlFor="query">研究问题</label>
            <div className="select-row">
              <select
                aria-label="模型 Provider"
                value={provider}
                disabled={isRunning || isRestoring}
                onChange={(event) => {
                  setProvider(event.target.value as ProviderName);
                  setModel("");
                }}
              >
                {providers.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <select
                aria-label="模型"
                value={selectedModel}
                disabled={isRunning || isRestoring || provider === "mock"}
                onChange={(event) => setModel(event.target.value)}
              >
                {currentModelOptions.map((item) => (
                  <option key={`${provider}-${item.id || "default"}`} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <textarea
            id="query"
            value={query}
            disabled={isRunning || isRestoring}
            onChange={(event) => setQuery(event.target.value)}
            rows={5}
          />

          <div className="control-row">
            <div className="mode-tabs" role="tablist" aria-label="研究模式">
              {modes.map((item) => (
                <button
                  key={item.value}
                  className={mode === item.value ? "mode-tab active" : "mode-tab"}
                  role="tab"
                  aria-selected={mode === item.value}
                  type="button"
                  disabled={isRunning || isRestoring}
                  onClick={() => setMode(item.value)}
                >
                  <span>{item.label}</span>
                  <small>{item.detail}</small>
                </button>
              ))}
            </div>

            <div className="action-buttons">
              {isRunning ? (
                <button
                  className="cancel-button"
                  type="button"
                  disabled={isCancelling}
                  onClick={handleCancel}
                >
                  {isCancelling ? <Loader2 className="spin" size={17} /> : <Square size={15} />}
                  {isCancelling ? "正在停止" : "停止"}
                </button>
              ) : null}
              <button
                className="submit-button"
                type="submit"
                disabled={isRunning || isRestoring || !query.trim()}
              >
                {isRestoring ? <Loader2 className="spin" size={18} /> : <ArrowRight size={18} />}
                {isRestoring ? "正在恢复" : "开始"}
              </button>
            </div>
          </div>
        </form>

        {error ? <div className="error-line">{error}</div> : null}

        <div className="timeline">
          <div className="section-title">
            <Sparkles size={17} />
            研究进度
          </div>
          {events.length === 0 ? (
            <div className="empty-state">
              <PauseCircle size={18} />
              等待任务开始
            </div>
          ) : (
            events.map((event) => (
              <div className="event-row" key={event.id}>
                <div className="event-icon">{getEventIcon(event.type)}</div>
                <div>
                  <strong>{event.message}</strong>
                  <span>{new Date(event.created_at).toLocaleTimeString("zh-CN")}</span>
                  <EventDetail event={event} />
                </div>
              </div>
            ))
          )}
        </div>

        {liveModelText ? (
          <div className="stream-panel">
            <div className="section-title compact-title">
              <Bot size={15} />
              模型实时输出
            </div>
            <pre>{liveModelText}</pre>
          </div>
        ) : null}
      </section>

      <aside className="report-panel">
        <div className="section-title">
          <FileText size={17} />
          研究报告
        </div>
        <article className="report-body">
          {report ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={reportMarkdownComponents}>
              {reportMarkdown}
            </ReactMarkdown>
          ) : (
            "报告将在研究完成后显示。"
          )}
        </article>

        <div className="source-list">
          <div className="section-title">
            <Search size={17} />
            来源
          </div>
          {sources.length === 0 ? (
            <span className="muted">暂无来源</span>
          ) : (
            sources.map((source) => <SourceCard key={source.url} source={source} />)
          )}
          {sources.length ? (
            <div className="reference-list">
              <div className="section-title compact-title">参考文献</div>
              {sources.map((source) => (
                <p key={`reference-${source.url}`}>{formatApaReference(source)}</p>
              ))}
            </div>
          ) : null}
        </div>
      </aside>
    </main>
  );
}
