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
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { createResearchEventSource, createResearchJob, getModelOptions } from "@/lib/api";
import type { ModelOption, ProviderName, ResearchEvent, ResearchMode } from "@/lib/types";

const modes: Array<{ value: ResearchMode; label: string; detail: string }> = [
  { value: "quick", label: "快速", detail: "少量来源" },
  { value: "deep", label: "深度", detail: "均衡研究" },
  { value: "expert", label: "专家", detail: "更强验证" },
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
  title: string;
  url: string;
  snippet?: string;
  query?: string;
};

function getEventIcon(type: string) {
  if (type === "completed") return <CheckCircle2 size={16} />;
  if (type.startsWith("tool")) return <Search size={16} />;
  if (type.startsWith("llm")) return <Bot size={16} />;
  return <Sparkles size={16} />;
}

function parseSources(rawSources: unknown): SourceItem[] {
  if (!Array.isArray(rawSources)) return [];
  return rawSources.flatMap((source, index) => {
    if (!source || typeof source !== "object") return [];
    const maybeSource = source as {
      citation_id?: unknown;
      title?: unknown;
      url?: unknown;
      snippet?: unknown;
      query?: unknown;
    };
    if (typeof maybeSource.url !== "string") return [];
    return [
      {
        citationId: typeof maybeSource.citation_id === "string" ? maybeSource.citation_id : String(index + 1),
        title: typeof maybeSource.title === "string" ? maybeSource.title : maybeSource.url,
        url: maybeSource.url,
        snippet: typeof maybeSource.snippet === "string" ? maybeSource.snippet : undefined,
        query: typeof maybeSource.query === "string" ? maybeSource.query : undefined,
      },
    ];
  });
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

function renderReportWithCitations(report: string, sourceByCitation: Map<string, SourceItem>) {
  const parts = report.split(/(\[(\d+)\])/g);
  return parts.map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    if (!match) return <span key={`${index}-${part.slice(0, 8)}`}>{part}</span>;
    const source = sourceByCitation.get(match[1]);
    if (!source) return <span key={`${index}-${part}`}>{part}</span>;
    return (
      <sup className="citation-mark" key={`${index}-${part}`} title={`${source.title}\n${source.url}`}>
        {part}
      </sup>
    );
  });
}

function SourceCard({ source }: { source: SourceItem }) {
  const icon = faviconUrl(source.url);
  return (
    <a className="source-card" href={source.url} rel="noreferrer" target="_blank">
      <div className="source-topline">
        <span className="source-favicon" style={icon ? { backgroundImage: `url(${icon})` } : undefined} />
        <span className="source-citation">[{source.citationId}]</span>
        <span className="source-domain">{hostname(source.url)}</span>
        <ExternalLink size={13} />
      </div>
      <strong>{source.title}</strong>
      {source.snippet ? <small>{source.snippet}</small> : null}
      <span className="source-url">{source.url}</span>
    </a>
  );
}

function EventDetail({ event }: { event: ResearchEvent }) {
  if (event.type === "tool_result") {
    const eventSources = parseSources(event.payload.sources);
    return eventSources.length ? (
      <div className="event-source-grid">
        {eventSources.map((source) => (
          <SourceCard key={`${event.id}-${source.citationId}-${source.url}`} source={source} />
        ))}
      </div>
    ) : null;
  }

  if (event.type === "evidence_required") {
    const missing = event.payload.missing;
    return Array.isArray(missing) ? <p className="event-note">补充步骤：{missing.join("、")}</p> : null;
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
  const [jobId, setJobId] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);

  const sources = useMemo(() => {
    const seen = new Set<string>();
    const items: SourceItem[] = [];
    for (const event of events) {
      for (const source of parseSources(event.payload.sources)) {
        if (seen.has(source.url)) continue;
        seen.add(source.url);
        items.push(source);
      }
    }
    return items;
  }, [events]);

  const sourceByCitation = useMemo(() => {
    return new Map(sources.map((source) => [source.citationId, source]));
  }, [sources]);

  const currentModelOptions = modelOptions[provider] ?? fallbackModelOptions[provider];
  const selectedModel = currentModelOptions.some((item) => item.id === model)
    ? model
    : currentModelOptions[0]?.id ?? "";

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
        if (providers.some((item) => item.value === defaultProvider)) {
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || isRunning) return;

    setError("");
    setEvents([]);
    setReport("");
    setIsRunning(true);

    try {
      const job = await createResearchJob({ query, mode, provider, model: selectedModel || undefined });
      setJobId(job.id);
      eventSourceRef.current?.close();
      const eventSource = createResearchEventSource(job.id);
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (message) => {
        const nextEvent = JSON.parse(message.data) as ResearchEvent;
        setEvents((current) => [...current, nextEvent]);
        if (nextEvent.type === "completed") {
          const finalReport = nextEvent.payload.final_report;
          if (typeof finalReport === "string") {
            setReport(finalReport);
          }
          setIsRunning(false);
          eventSource.close();
          eventSourceRef.current = null;
        }
        if (nextEvent.type === "report_delta") {
          const delta = nextEvent.payload.delta;
          if (typeof delta === "string") {
            setReport((current) => current + delta);
          }
        }
        if (nextEvent.type === "failed") {
          setError(nextEvent.message);
          setIsRunning(false);
          eventSource.close();
          eventSourceRef.current = null;
        }
      };

      eventSource.onerror = () => {
        setError("事件流连接中断");
        setIsRunning(false);
        eventSource.close();
        eventSourceRef.current = null;
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建研究任务失败");
      setIsRunning(false);
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
          <strong>{jobId ? jobId.slice(0, 10) : "尚未创建"}</strong>
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
                disabled={provider === "mock"}
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
                  onClick={() => setMode(item.value)}
                >
                  <span>{item.label}</span>
                  <small>{item.detail}</small>
                </button>
              ))}
            </div>

            <button className="submit-button" type="submit" disabled={isRunning || !query.trim()}>
              {isRunning ? <Loader2 className="spin" size={18} /> : <ArrowRight size={18} />}
              {isRunning ? "研究中" : "开始"}
            </button>
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
      </section>

      <aside className="report-panel">
        <div className="section-title">
          <FileText size={17} />
          研究报告
        </div>
        <article className="report-body">
          {report ? renderReportWithCitations(report, sourceByCitation) : "报告将在研究完成后显示。"}
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
