"use client";

import { Accordion, Button, Card, Spinner, TextArea } from "@heroui/react";
import {
  Bot,
  CheckCircle2,
  Download,
  FileDown,
  RotateCcw,
  Search,
  Sparkles,
  Square,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

import { useAppAuth } from "@/components/app-auth-provider";
import { LanguageSwitch } from "@/components/language-switch";
import { ResearchModeTabs } from "@/components/research-mode-tabs";
import {
  CitationLink,
  formatApaReference,
  isVisitedSource,
  markdownWithCitationLinks,
  nodeText,
  parseSources,
  SourceCardItem,
  type SourceItem,
} from "@/components/research-sources";
import {
  MobileSourcesModal,
  SourcesRail,
  WorkbenchSidebar,
} from "@/components/research-workspace-panels";
import {
  ApiError,
  EVENT_STREAM_CLOSED,
  cancelResearchJob,
  createResearchEventSource,
  createResearchJob,
  exportResearchJobPdf,
  getModelOptions,
  getResearchEvents,
  getResearchJob,
  listResearchJobs,
  rerunResearchJob,
  retryResearchJob,
} from "@/lib/api";
import type { ResearchEventStream } from "@/lib/api";
import { consumeHandoff } from "@/lib/handoff";
import { useI18n } from "@/lib/i18n";
import { downloadBlobFile, downloadMarkdownReport } from "@/lib/markdown-export";
import type { ModelOption, ProviderName, ResearchEvent, ResearchJob, ResearchMode } from "@/lib/types";

const ACTIVE_JOB_STORAGE_KEY = "pz-deep-research-active-job";
const RESTORE_TIMEOUT_MS = 4_000;

type WorkbenchView = "empty" | "run" | "report" | "failed";

const fallbackModelOptions: Record<ProviderName, ModelOption[]> = {
  mock: [{ id: "", label: "Dev mode" }],
  openai: [
    { id: "gpt-5.4-mini", label: "gpt-5.4-mini" },
    { id: "gpt-5.5", label: "gpt-5.5" },
    { id: "gpt-5.4", label: "gpt-5.4" },
    { id: "gpt-5.4-nano", label: "gpt-5.4-nano" },
    { id: "gpt-5-mini", label: "gpt-5-mini" },
    { id: "gpt-5-nano", label: "gpt-5-nano" },
  ],
  anthropic: [
    { id: "claude-sonnet-4-6", label: "claude-sonnet-4-6" },
    { id: "claude-opus-4-8", label: "claude-opus-4-8" },
    { id: "claude-opus-4-7", label: "claude-opus-4-7" },
    { id: "claude-opus-4-6", label: "claude-opus-4-6" },
    { id: "claude-haiku-4-5-20251001", label: "claude-haiku-4-5-20251001" },
  ],
  gemini: [
    { id: "gemini-3.5-flash", label: "gemini-3.5-flash" },
    { id: "gemini-3.1-pro-preview", label: "gemini-3.1-pro-preview" },
    { id: "gemini-3-flash-preview", label: "gemini-3-flash-preview" },
    { id: "gemini-3.1-flash-lite", label: "gemini-3.1-flash-lite" },
    { id: "gemini-2.5-pro", label: "gemini-2.5-pro" },
    { id: "gemini-2.5-flash", label: "gemini-2.5-flash" },
    { id: "gemini-2.5-flash-lite", label: "gemini-2.5-flash-lite" },
  ],
};

const PROVIDER_ORDER: ProviderName[] = ["mock", "openai", "anthropic", "gemini"];

function isProviderName(value: string): value is ProviderName {
  return PROVIDER_ORDER.includes(value as ProviderName);
}

function mergeEvent(current: ResearchEvent[], nextEvent: ResearchEvent) {
  if (current.some((event) => event.id === nextEvent.id)) return current;
  return [...current, nextEvent];
}

export function ResearchWorkspace() {
  const { t, locale } = useI18n();
  const { isLoaded: isAuthLoaded, isSignedIn, userId } = useAppAuth();

  const evidenceLabel = useCallback(
    (source: SourceItem) => {
      const value = source.evidenceLevel || source.readStatus;
      const labels: Record<string, string> =
        locale === "zh"
          ? {
              full_text: "全文证据",
              partial_text: "部分正文",
              metadata_only: "访问受限",
              metadata: "题录摘要",
              mock: "开发占位",
              unavailable: "不可用",
            }
          : {
              full_text: "Full-text evidence",
              partial_text: "Partial text",
              metadata_only: "Limited access",
              metadata: "Metadata only",
              mock: "Dev placeholder",
              unavailable: "Unavailable",
            };
      if (value && labels[value]) return labels[value];
      return value || (locale === "zh" ? "未分级" : "Ungraded");
    },
    [locale],
  );

  const jobStatusLabel = useCallback(
    (status: ResearchJob["status"] | "") => {
      if (status === "queued") return t.status.queued;
      if (status === "running") return t.status.running;
      if (status === "completed") return t.status.completed;
      if (status === "failed") return t.status.failed;
      if (status === "cancelled") return t.status.cancelled;
      return t.status.idle;
    },
    [t],
  );

  const formatDateTime = useCallback(
    (value: string) =>
      new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value)),
    [locale],
  );

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ResearchMode>("deep");
  const [provider, setProvider] = useState<ProviderName>("mock");
  const [model, setModel] = useState("");
  // BYOK key: kept in memory only (never persisted), sent per request in community edition.
  const [apiKey, setApiKey] = useState("");
  const [modelOptions, setModelOptions] = useState(fallbackModelOptions);
  const [modelSelectionEnabled, setModelSelectionEnabled] = useState(false);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [report, setReport] = useState("");
  const [liveModelText, setLiveModelText] = useState("");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState<ResearchJob["status"] | "">("");
  const [isRunning, setIsRunning] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [view, setView] = useState<WorkbenchView>("empty");
  const [historyJobs, setHistoryJobs] = useState<ResearchJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<ResearchJob | null>(null);
  const [error, setError] = useState("");
  const [errorRetryable, setErrorRetryable] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const eventSourceRef = useRef<ResearchEventStream | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const showToast = useCallback((message: string) => {
    setToastMessage(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToastMessage(""), 2600);
  }, []);

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

  const reportMarkdownComponents = useMemo<Components>(() => {
    return {
      a({ href, children }) {
        const text = nodeText(children);
        const match = /^\[(\d+)\]$/.exec(text);
        if (match) {
          const source = sourceByCitation.get(match[1]);
          return (
            <CitationLink evidenceLabel={evidenceLabel} href={href} source={source}>
              {children}
            </CitationLink>
          );
        }
        return (
          <a href={href} rel="noreferrer" target="_blank">
            {children}
          </a>
        );
      },
    };
  }, [sourceByCitation, evidenceLabel]);

  const currentModelOptions = modelOptions[provider] ?? fallbackModelOptions[provider];
  const selectedModel = currentModelOptions.some((item) => item.id === model)
    ? model
    : currentModelOptions[0]?.id ?? "";

  const connectToJob = useCallback(
    (targetJobId: string, afterEventId?: string) => {
      eventSourceRef.current?.close();
      const eventSource = createResearchEventSource(targetJobId, afterEventId);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setError((current) => (current.startsWith(t.errors.networkUnstable.slice(0, 6)) ? "" : current));
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
              setErrorRetryable(Boolean(nextEvent.payload.error_retryable));
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
          setError("");
          setErrorRetryable(false);
          setSelectedJob((current) => (
            current?.id === targetJobId ? { ...current, status: "completed", error: null } : current
          ));
          setIsRunning(false);
          setView("report");
          showToast(t.wb.reportReady);
          eventSource.close();
          if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
        }
        if (nextEvent.type === "failed") {
          setError(nextEvent.message);
          setErrorRetryable(Boolean(nextEvent.payload.retryable));
          setJobStatus("failed");
          setSelectedJob((current) => (
            current?.id === targetJobId
              ? {
                  ...current,
                  status: "failed",
                  error: nextEvent.message,
                  error_retryable: Boolean(nextEvent.payload.retryable),
                  error_stage: typeof nextEvent.payload.stage === "string" ? nextEvent.payload.stage : null,
                }
              : current
          ));
          setIsRunning(false);
          setView("failed");
          eventSource.close();
          if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
        }
        if (nextEvent.type === "cancelled") {
          setJobStatus("cancelled");
          setIsRunning(false);
          setIsCancelling(false);
          setView("report");
          eventSource.close();
          if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
        }
      };

      eventSource.onerror = () => {
        if (eventSource.readyState !== EVENT_STREAM_CLOSED) {
          setError(t.errors.networkUnstable);
          setErrorRetryable(false);
          return;
        }
        setError(t.errors.connectionLost);
        setErrorRetryable(false);
        setIsRunning(false);
        if (eventSourceRef.current === eventSource) eventSourceRef.current = null;
      };
    },
    [showToast, t],
  );

  const restoreJob = useCallback(
    async (targetJobId: string) => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), RESTORE_TIMEOUT_MS);
      const [job, restoredEvents] = await Promise.all([
        getResearchJob(targetJobId, controller.signal),
        getResearchEvents(targetJobId, controller.signal),
      ]).finally(() => window.clearTimeout(timeout));
      setJobId(job.id);
      setSelectedJob(job);
      setJobStatus(job.status);
      setQuery(job.query);
      setMode(job.mode);
      if (isProviderName(job.provider)) setProvider(job.provider);
      setModel(job.model || "");
      setEvents(restoredEvents);
      setReport(job.final_report || job.draft_report || "");
      setLiveModelText("");
      setError(job.error || "");
      setErrorRetryable(Boolean(job.error_retryable));
      window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, job.id);

      const shouldResume = job.status === "queued" || job.status === "running";
      setIsRunning(shouldResume);
      if (shouldResume) {
        setView("run");
        connectToJob(job.id, restoredEvents.at(-1)?.id);
      } else {
        setView(job.status === "failed" ? "failed" : "report");
        eventSourceRef.current?.close();
        eventSourceRef.current = null;
      }
      return job;
    },
    [connectToJob],
  );

  const refreshHistory = useCallback(async () => {
    try {
      setHistoryJobs(await listResearchJobs());
    } catch {
      // keep the previous list on failure; non-fatal for the workbench
    }
  }, []);

  const startResearch = useCallback(
    async (queryText: string, modeValue: ResearchMode) => {
      const trimmed = queryText.trim();
      if (!trimmed) return;

      setError("");
      setErrorRetryable(false);
      setEvents([]);
      setReport("");
      setLiveModelText("");
      setIsRunning(true);
      setJobStatus("queued");
      setView("run");
      setMenuOpen(false);

      try {
        const trimmedKey = apiKey.trim();
        const job = await createResearchJob({
          query: trimmed,
          mode: modeValue,
          ...(modelSelectionEnabled ? { provider, model: selectedModel || undefined } : {}),
          ...(modelSelectionEnabled && provider !== "mock" && trimmedKey
            ? { api_key: trimmedKey }
            : {}),
        });
        setJobId(job.id);
        setSelectedJob(job);
        setJobStatus(job.status);
        window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, job.id);
        connectToJob(job.id);
        setHistoryJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      } catch (err) {
        setError(err instanceof Error ? err.message : t.errors.createFailed);
        setErrorRetryable(err instanceof ApiError ? err.retryable : false);
        setIsRunning(false);
        setJobStatus("failed");
        setView("failed");
      }
    },
    [apiKey, connectToJob, modelSelectionEnabled, provider, selectedModel, t],
  );

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    };
  }, []);

  useEffect(() => {
    let ignore = false;
    getModelOptions()
      .then((payload) => {
        if (ignore) return;
        setModelSelectionEnabled(payload.selection_enabled);
        setModelOptions({ ...fallbackModelOptions, ...payload.providers });
        const defaultProvider = payload.defaults.provider;
        if (!window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY) && isProviderName(defaultProvider)) {
          setProvider(defaultProvider);
        }
      })
      .catch(() => {
        // fall back to the local provider/model list; UI stays usable
      });
    return () => {
      ignore = true;
    };
  }, []);

  // Boot: handoff from the marketing homepage takes priority, then restore an active job.
  useEffect(() => {
    if (!isAuthLoaded) return;
    let ignore = false;

    const handoff = consumeHandoff();
    if (handoff) {
      const timer = window.setTimeout(() => {
        if (ignore) return;
        setQuery(handoff.query);
        setMode(handoff.mode);
        setIsRestoring(false);
        if (handoff.autostart) void startResearch(handoff.query, handoff.mode);
      }, 0);
      return () => {
        ignore = true;
        window.clearTimeout(timer);
      };
    }

    const storedJobId = window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
    if (!storedJobId) {
      return () => {
        ignore = true;
      };
    }

    const timer = window.setTimeout(() => {
      setIsRestoring(true);
      restoreJob(storedJobId)
        .catch(() => {
          if (ignore) return;
          window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
          setJobId("");
          setJobStatus("");
          setView("empty");
        })
        .finally(() => {
          if (!ignore) setIsRestoring(false);
        });
    }, 0);

    return () => {
      ignore = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthLoaded, userId]);

  // Keep the sidebar history fresh once auth resolves.
  useEffect(() => {
    if (!isAuthLoaded) return;
    const timer = window.setTimeout(() => void refreshHistory(), 0);
    return () => window.clearTimeout(timer);
  }, [isAuthLoaded, isSignedIn, refreshHistory, userId]);

  // Mobile sidebar state is reflected on the body for the CSS drawer.
  useEffect(() => {
    document.body.classList.toggle("menu-open", menuOpen);
    return () => {
      document.body.classList.remove("menu-open");
    };
  }, [menuOpen]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isRunning || isRestoring) return;
    void startResearch(query, mode);
  }

  async function handleCancel() {
    if (!jobId || !isRunning || isCancelling) return;
    setIsCancelling(true);
    setError("");
    setErrorRetryable(false);
    try {
      const cancelledJob = await cancelResearchJob(jobId);
      const restoredEvents = await getResearchEvents(jobId);
      setEvents(restoredEvents);
      setReport(cancelledJob.final_report || cancelledJob.draft_report || "");
      setSelectedJob(cancelledJob);
      setJobStatus("cancelled");
      setIsRunning(false);
      setView("report");
      showToast(t.wb.cancelled);
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    } catch (err) {
      setError(err instanceof Error ? err.message : t.errors.cancelFailed);
      setErrorRetryable(err instanceof ApiError ? err.retryable : false);
    } finally {
      setIsCancelling(false);
    }
  }

  async function handleRerun() {
    if (!selectedJob || isRerunning || selectedJob.status === "queued" || selectedJob.status === "running") {
      return;
    }
    setIsRerunning(true);
    setError("");
    setErrorRetryable(false);
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    try {
      const rerunJob = await rerunResearchJob(selectedJob.id);
      setSelectedJob(rerunJob);
      setJobId(rerunJob.id);
      setJobStatus(rerunJob.status);
      setQuery(rerunJob.query);
      setMode(rerunJob.mode);
      if (isProviderName(rerunJob.provider)) setProvider(rerunJob.provider);
      setModel(rerunJob.model || "");
      setEvents([]);
      setReport("");
      setLiveModelText("");
      setIsRunning(true);
      setView("run");
      window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, rerunJob.id);
      setHistoryJobs((current) => [rerunJob, ...current.filter((item) => item.id !== rerunJob.id)]);
      connectToJob(rerunJob.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.errors.rerunFailed);
      setErrorRetryable(err instanceof ApiError ? err.retryable : false);
    } finally {
      setIsRerunning(false);
    }
  }

  async function handleRetry() {
    if (!jobId || isRerunning || jobStatus !== "failed" || !errorRetryable) return;
    setIsRerunning(true);
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    try {
      const retryJob = await retryResearchJob(jobId);
      setSelectedJob(retryJob);
      setJobId(retryJob.id);
      setJobStatus(retryJob.status);
      setQuery(retryJob.query);
      setMode(retryJob.mode);
      if (isProviderName(retryJob.provider)) setProvider(retryJob.provider);
      setModel(retryJob.model || "");
      setEvents([]);
      setReport("");
      setLiveModelText("");
      setError("");
      setErrorRetryable(false);
      setIsRunning(true);
      setView("run");
      window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, retryJob.id);
      setHistoryJobs((current) => [retryJob, ...current.filter((item) => item.id !== retryJob.id)]);
      connectToJob(retryJob.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.errors.retryFailed);
      setErrorRetryable(err instanceof ApiError ? err.retryable : true);
    } finally {
      setIsRerunning(false);
    }
  }

  async function handlePdfExport() {
    if (!jobId || !report || isRunning || isExportingPdf) return;
    setIsExportingPdf(true);
    setError("");
    try {
      const pdf = await exportResearchJobPdf(jobId);
      downloadBlobFile(pdf.blob, pdf.filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.errors.pdfFailed);
    } finally {
      setIsExportingPdf(false);
    }
  }

  function handleNewResearch() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
    setView("empty");
    setMenuOpen(false);
    setRailOpen(false);
    setJobId("");
    setJobStatus("");
    setSelectedJob(null);
    setEvents([]);
    setReport("");
    setLiveModelText("");
    setQuery("");
    setError("");
    setErrorRetryable(false);
    setIsRunning(false);
  }

  function openHistoryJob(job: ResearchJob) {
    setMenuOpen(false);
    setIsRestoring(true);
    restoreJob(job.id)
      .catch((err) => {
        setError(err instanceof Error ? err.message : t.errors.detailFailed);
      })
      .finally(() => setIsRestoring(false));
  }

  const railSources = sources;
  const railShown = view === "run" || view === "report";
  const crumbCurrent =
    view === "run"
      ? t.wb.crumbResearching
      : view === "empty"
        ? t.wb.crumbNew
        : query || t.wb.crumbNew;

  function getEventNode(type: string) {
    if (type === "completed") return <CheckCircle2 size={15} />;
    if (type === "cancelled") return <Square size={14} />;
    if (type.startsWith("tool")) return <Search size={15} />;
    if (type.startsWith("llm")) return <Bot size={15} />;
    return <Sparkles size={15} />;
  }

  function renderEventDetail(event: ResearchEvent) {
    if (event.type === "tool_result") {
      const eventSources = parseSources(event.payload.sources);
      const content = event.payload.content;
      return (
        <>
          {typeof content === "string" && content ? (
            <Accordion className="tool-output">
              <Accordion.Item id={`tool-${event.id}`}>
                <Accordion.Heading>
                  <Accordion.Trigger className="tool-output-trigger">
                    {locale === "zh" ? "查看工具返回" : "View tool output"}
                    <Accordion.Indicator />
                  </Accordion.Trigger>
                </Accordion.Heading>
                <Accordion.Panel>
                  <Accordion.Body><pre>{content}</pre></Accordion.Body>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          ) : null}
          {eventSources.length ? (
            <div className="event-source-grid">
              {eventSources.map((source) => (
                <SourceCardItem
                  key={`${event.id}-${source.citationId}-${source.url}`}
                  source={source}
                  evidenceLabel={evidenceLabel}
                />
              ))}
            </div>
          ) : null}
        </>
      );
    }
    if (event.type === "llm_result") {
      const preview = event.payload.content_preview;
      return typeof preview === "string" && preview ? <p className="t-line">{preview}</p> : null;
    }
    if (event.type === "visit_progress") {
      const visited = event.payload.visited;
      const target = event.payload.target;
      const fullText = event.payload.full_text;
      if (typeof visited === "number" && typeof target === "number") {
        return (
          <p className="t-line mono">
            {locale === "zh" ? `已访问 ${visited} 个候选来源` : `${visited} candidate sources visited`}
            {typeof fullText === "number"
              ? locale === "zh"
                ? `，全文证据 ${fullText}/${target} 个`
                : ` · full-text ${fullText}/${target}`
              : ""}
          </p>
        );
      }
    }
    if (event.type === "evidence_ready") {
      const total = event.payload.total_cards;
      return typeof total === "number" ? (
        <p className="t-line mono">
          {locale === "zh" ? `已抽取证据卡片 ${total} 张` : `${total} evidence cards extracted`}
        </p>
      ) : null;
    }
    if (event.type === "source_selected") {
      const selected = event.payload.selected_count;
      const target = event.payload.target;
      const fullText = event.payload.full_text_count;
      return (
        <p className="t-line mono">
          {locale === "zh" ? "已筛选来源：最终 " : "Sources selected: "}
          {typeof selected === "number" ? selected : "?"}
          {typeof target === "number" ? `/${target}` : ""}
          {typeof fullText === "number"
            ? locale === "zh"
              ? `，全文证据 ${fullText} 个`
              : ` · ${fullText} full-text`
            : ""}
        </p>
      );
    }
    return null;
  }

  /* ---------- view bodies ---------- */

  function renderEmpty() {
    return (
      <div className="empty-state">
        <h1>{t.wb.emptyTitle}</h1>
        <p className="sub">{t.wb.emptySub}</p>

        <form onSubmit={handleSubmit}>
          <Card className="ask-box flow-ring" variant="secondary">
            <label className="sr-only" htmlFor="wb-ask">{t.wb.emptyTitle}</label>
            <TextArea
              id="wb-ask"
              rows={2}
              placeholder={t.wb.askPlaceholder}
              value={query}
              disabled={isRunning || isRestoring}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (query.trim()) void startResearch(query, mode);
                }
              }}
              variant="secondary"
            />
            <div className="ask-foot">
              <ResearchModeTabs
                ariaLabel={t.nav.modes}
                disabled={isRunning || isRestoring}
                labels={t.modes}
                mode={mode}
                onModeChange={setMode}
              />
              <Button className="go" type="submit" isDisabled={isRunning || isRestoring || !query.trim()} variant="primary">
                {isRestoring ? <Spinner size="sm" /> : null}
                {t.home.startResearch}
              </Button>
            </div>
          </Card>
        </form>

        {modelSelectionEnabled ? (
          <Accordion className="adv" variant="surface">
            <Accordion.Item id="advanced-model-settings">
              <Accordion.Heading>
                <Accordion.Trigger className="adv-trigger">
                  {t.wb.advanced}
                  <Accordion.Indicator />
                </Accordion.Trigger>
              </Accordion.Heading>
              <Accordion.Panel>
                <Accordion.Body>
                  <div className="adv-grid">
                    <div className="adv-field">
                      <label htmlFor="adv-provider">Provider</label>
                      <select
                        id="adv-provider"
                        value={provider}
                        disabled={isRunning || isRestoring}
                        onChange={(event) => {
                          setProvider(event.target.value as ProviderName);
                          setModel("");
                        }}
                      >
                        {PROVIDER_ORDER.map((value) => (
                          <option key={value} value={value}>{t.providers[value]}</option>
                        ))}
                      </select>
                    </div>
                    <div className="adv-field">
                      <label htmlFor="adv-model">Model</label>
                      <select
                        id="adv-model"
                        value={selectedModel}
                        disabled={isRunning || isRestoring || provider === "mock"}
                        onChange={(event) => setModel(event.target.value)}
                      >
                        {currentModelOptions.map((item) => (
                          <option key={`${provider}-${item.id || "default"}`} value={item.id}>{item.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  {provider !== "mock" ? (
                    <div className="adv-field adv-byok">
                      <label htmlFor="adv-api-key">{t.wb.byokLabel}</label>
                      <input
                        id="adv-api-key"
                        type="password"
                        autoComplete="off"
                        value={apiKey}
                        disabled={isRunning || isRestoring}
                        placeholder={t.wb.byokPlaceholder}
                        onChange={(event) => setApiKey(event.target.value)}
                      />
                      <p className="adv-hint">{t.wb.byokHint}</p>
                    </div>
                  ) : null}
                </Accordion.Body>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        ) : null}

        <div className="recent-block">
          <h2>{t.wb.recentTitle}</h2>
          {historyJobs.length === 0 ? (
            <p className="recent-empty">{t.wb.recentEmpty}</p>
          ) : (
            <div className="recent-grid">
              {historyJobs.slice(0, 6).map((job) => (
                <Button key={job.id} className="recent-card" onPress={() => openHistoryJob(job)} variant="ghost">
                  <span className="q">{job.query}</span>
                  <span className="m">
                    <span className={`s-dot${job.status === "failed" ? " failed" : ""}`} />
                    {t.modes[job.mode]} · {formatDateTime(job.updated_at)}
                    {job.status === "failed" ? (locale === "zh" ? " · 失败" : " · failed") : ""}
                  </span>
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  function renderRun() {
    return (
      <>
        <div className="run-head">
          <p className="q-label">{t.modes[mode]} {t.wb.runLabelSuffix}</p>
          <h1>{query}</h1>
          <div className="run-meta">
            <span className="chip"><span className="dot live" />{t.wb.running}</span>
            {jobId ? <span className="chip mono">{jobId}</span> : null}
          </div>
        </div>

        {error ? <ErrorNotice message={error} /> : null}

        <div className="timeline">
          {events.length === 0 ? (
            <div className="t-step" data-state="active">
              <div className="t-node"><Spinner color="current" size="sm" /></div>
              <div className="t-title"><span className="shimmer">{t.wb.crumbResearching}</span></div>
            </div>
          ) : (
            events.map((event) => (
              <div className="t-step" data-state="done" key={event.id}>
                <div className="t-node">{getEventNode(event.type)}</div>
                <div className="t-title">{event.message}</div>
                <div className="t-detail">
                  {renderEventDetail(event)}
                  <span className="t-time mono">{new Date(event.created_at).toLocaleTimeString(locale === "zh" ? "zh-CN" : "en-US")}</span>
                </div>
              </div>
            ))
          )}
          {isRunning && events.length > 0 ? (
            <div className="t-step" data-state="active">
              <div className="t-node"><Spinner color="current" size="sm" /></div>
              <div className="t-title">
                <span className="shimmer">{liveModelText ? t.wb.liveOutput : t.wb.crumbResearching}</span>
              </div>
              {liveModelText ? (
                <div className="t-detail">
                  <Card className="draft-preview" variant="secondary">{liveModelText}</Card>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="run-actions">
          {isRunning ? (
            <Button size="sm" variant="danger-soft" isDisabled={isCancelling} onPress={handleCancel}>
              {isCancelling ? <Spinner color="current" size="sm" /> : <Square size={14} />}
              {isCancelling ? t.wb.stopping : t.wb.cancel}
            </Button>
          ) : null}
        </div>
      </>
    );
  }

  function renderReport() {
    const status = selectedJob?.status ?? jobStatus;
    return (
      <>
        <div className="report-head">
          <p className="q-label kicker">{t.modes[mode]} {t.wb.reportLabelSuffix}</p>
          <h1>{query}</h1>
          <div className="run-meta">
            <span className="chip"><b>{sources.length}</b>&nbsp;{t.wb.sourcesCited}</span>
            <span className={`job-status ${status || "idle"}`}>{jobStatusLabel(status)}</span>
            {jobId ? <span className="chip mono">{jobId}</span> : null}
            {selectedJob ? <span className="chip">{formatDateTime(selectedJob.updated_at)}</span> : null}
          </div>
          <div className="report-actions">
            <Button
              size="sm"
              variant="secondary"
              isDisabled={!report}
              onPress={() => downloadMarkdownReport({ query, report, jobId })}
            >
              <Download size={15} />{t.wb.exportMd}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              isDisabled={!report || !jobId || isRunning || isExportingPdf}
              onPress={() => void handlePdfExport()}
            >
              {isExportingPdf ? <Spinner color="current" size="sm" /> : <FileDown size={15} />}{t.wb.exportPdf}
            </Button>
            {selectedJob && selectedJob.status !== "failed" ? (
              <Button
                size="sm"
                variant="ghost"
                isDisabled={isRerunning || selectedJob.status === "queued" || selectedJob.status === "running"}
                onPress={() => void handleRerun()}
              >
                {isRerunning ? <Spinner color="current" size="sm" /> : <RotateCcw size={15} />}
                {isRerunning ? t.wb.rerunning : t.wb.rerun}
              </Button>
            ) : null}
          </div>
        </div>

        {error ? <ErrorNotice message={error} /> : null}

        <article className="report-body markdown-body">
          {report ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={reportMarkdownComponents}>
              {reportMarkdown}
            </ReactMarkdown>
          ) : (
            <p className="report-placeholder">{t.wb.reportPlaceholder}</p>
          )}
        </article>

        {sources.length ? (
          <div className="reference-list">
            <div className="ref-title">{t.wb.references}</div>
            {sources.map((source) => (
              <p key={`reference-${source.url}`}>{formatApaReference(source)}</p>
            ))}
          </div>
        ) : null}
      </>
    );
  }

  function renderFailed() {
    return (
      <>
        <div className="run-head">
          <p className="q-label">{t.modes[mode]} {t.wb.runLabelSuffix}</p>
          <h1>{query}</h1>
        </div>
        <Card className="fail-card" variant="tertiary">
          <h2>{error || t.wb.failTitle}</h2>
          <p>{t.wb.failBody}</p>
          {errorRetryable ? (
            <Button size="sm" variant="primary" isDisabled={isRerunning} onPress={() => void handleRetry()}>
              {isRerunning ? <Spinner color="current" size="sm" /> : <RotateCcw size={15} />}
              {isRerunning ? t.wb.retrying : t.wb.retry}
            </Button>
          ) : null}
        </Card>
      </>
    );
  }

  return (
    <>
      <div className="atmosphere" aria-hidden="true" />

      <div className="wb" data-rail={railShown ? "on" : "off"}>
        <WorkbenchSidebar
          formatDateTime={formatDateTime}
          historyJobs={historyJobs}
          jobId={jobId}
          onNewResearch={handleNewResearch}
          onOpenHistory={openHistoryJob}
        />

        {/* ---------- main ---------- */}
        <main className="main">
          <div className="topbar">
            <Button
              className="menu-btn"
              size="sm"
              variant="ghost"
              aria-label={t.wb.openMenu}
              onPress={() => setMenuOpen((open) => !open)}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </Button>
            <p className="crumb">{t.wb.crumbRoot} <span className="sep">/</span> <b>{crumbCurrent}</b></p>
            <span className="spacer" />
            <LanguageSwitch />
            {railShown ? (
              <MobileSourcesModal
                evidenceLabel={evidenceLabel}
                isOpen={railOpen}
                onOpenChange={setRailOpen}
                sources={railSources}
                view={view}
              />
            ) : null}
          </div>

          <div className="main-scroll">
            <div className="main-inner">
              {view === "empty"
                ? renderEmpty()
                : view === "run"
                  ? renderRun()
                  : view === "failed"
                    ? renderFailed()
                    : renderReport()}
            </div>
          </div>
        </main>

        <SourcesRail
          evidenceLabel={evidenceLabel}
          isRunning={isRunning}
          sources={railSources}
          view={view}
        />
      </div>

      <div
        className="scrim"
        onClick={() => {
          setMenuOpen(false);
        }}
      />
      <Card className={`toast${toastMessage ? " show" : ""}`} role="status" variant="tertiary">
        {toastMessage}
      </Card>
    </>
  );
}

function ErrorNotice({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="error-line" role="alert">
      <span>{message}</span>
    </div>
  );
}
