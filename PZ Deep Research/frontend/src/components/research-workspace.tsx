"use client";

import {
  ArrowRight,
  Bot,
  CheckCircle2,
  FileText,
  Loader2,
  PauseCircle,
  Search,
  Settings2,
  Sparkles,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { createResearchEventSource, createResearchJob } from "@/lib/api";
import type { ProviderName, ResearchEvent, ResearchMode } from "@/lib/types";

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

function getEventIcon(type: string) {
  if (type === "completed") return <CheckCircle2 size={16} />;
  if (type.startsWith("tool")) return <Search size={16} />;
  if (type.startsWith("llm")) return <Bot size={16} />;
  return <Sparkles size={16} />;
}

export function ResearchWorkspace() {
  const [query, setQuery] = useState("对比 Claude、ChatGPT 和 Gemini 做深度研究产品时各自的优势与风险");
  const [mode, setMode] = useState<ResearchMode>("deep");
  const [provider, setProvider] = useState<ProviderName>("mock");
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [report, setReport] = useState("");
  const [jobId, setJobId] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);

  const sources = useMemo(() => {
    const seen = new Set<string>();
    const items: Array<{ title: string; url: string }> = [];
    for (const event of events) {
      const rawSources = event.payload.sources;
      if (!Array.isArray(rawSources)) continue;
      for (const source of rawSources) {
        if (!source || typeof source !== "object") continue;
        const maybeSource = source as { title?: unknown; url?: unknown };
        if (typeof maybeSource.url !== "string" || seen.has(maybeSource.url)) continue;
        seen.add(maybeSource.url);
        items.push({
          title: typeof maybeSource.title === "string" ? maybeSource.title : maybeSource.url,
          url: maybeSource.url,
        });
      }
    }
    return items;
  }, [events]);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
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
      const job = await createResearchJob({ query, mode, provider });
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
                onChange={(event) => setProvider(event.target.value as ProviderName)}
              >
                {providers.map((item) => (
                  <option key={item.value} value={item.value}>
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
          {report ? report : "报告将在研究完成后显示。"}
        </article>

        <div className="source-list">
          <div className="section-title">
            <Search size={17} />
            来源
          </div>
          {sources.length === 0 ? (
            <span className="muted">暂无来源</span>
          ) : (
            sources.map((source) => (
              <a href={source.url} key={source.url} rel="noreferrer" target="_blank">
                {source.title}
              </a>
            ))
          )}
        </div>
      </aside>
    </main>
  );
}
