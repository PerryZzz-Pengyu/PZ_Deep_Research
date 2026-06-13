"use client";

import { Button, Card, Modal } from "@heroui/react";
import { Clock3 } from "lucide-react";
import Link from "next/link";

import { AccountControl } from "@/components/auth-controls";
import { BrandMark } from "@/components/brand-mark";
import { RailSourceCard, type SourceItem } from "@/components/research-sources";
import { useI18n } from "@/lib/i18n";
import type { ResearchJob } from "@/lib/types";

export function WorkbenchSidebar({
  formatDateTime,
  historyJobs,
  jobId,
  onNewResearch,
  onOpenHistory,
}: {
  formatDateTime: (value: string) => string;
  historyJobs: ResearchJob[];
  jobId: string;
  onNewResearch: () => void;
  onOpenHistory: (job: ResearchJob) => void;
}) {
  const { t } = useI18n();
  return (
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label={t.brand}>
        <BrandMark />
        <span>{t.brand}</span>
      </Link>

      <Button className="new-research" variant="primary" onPress={onNewResearch}>
        {t.wb.newResearch}
      </Button>

      <p className="side-label">{t.wb.fieldsLabel}</p>
      <ul className="field-list">
        <li><Button variant="ghost" aria-current="true"><span className="f-dot" />{t.wb.field.scholar}</Button></li>
        <li><Button variant="ghost" isDisabled><span className="f-dot" />{t.wb.field.finance}<span className="soon">{t.wb.soon}</span></Button></li>
        <li><Button variant="ghost" isDisabled><span className="f-dot" />{t.wb.field.legal}<span className="soon">{t.wb.soon}</span></Button></li>
        <li><Button variant="ghost" isDisabled><span className="f-dot" />{t.wb.field.biotech}<span className="soon">{t.wb.soon}</span></Button></li>
      </ul>

      <p className="side-label">{t.wb.historyLabel}</p>
      <div className="history-scroll">
        {historyJobs.length === 0 ? (
          <p className="history-empty"><Clock3 size={14} />{t.wb.recentEmpty}</p>
        ) : (
          <ul className="history-list">
            {historyJobs.map((job) => (
              <li key={job.id}>
                <Button
                  variant="ghost"
                  aria-current={job.id === jobId ? "true" : undefined}
                  onPress={() => onOpenHistory(job)}
                >
                  <span className="h-q">{job.query}</span>
                  <span className="h-meta">
                    <span className={`s-dot${job.status === "failed" ? " failed" : ""}`} />
                    {t.modes[job.mode]} · {formatDateTime(job.updated_at)}
                  </span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Card className="user-card" variant="secondary">
        <AccountControl />
      </Card>
    </aside>
  );
}

function SourceList({
  emptyMessage,
  evidenceLabel,
  sources,
}: {
  emptyMessage: string;
  evidenceLabel: (source: SourceItem) => string;
  sources: SourceItem[];
}) {
  if (sources.length === 0) return <p className="rail-empty">{emptyMessage}</p>;
  return (
    <div className="source-modal-list">
      {sources.map((source, index) => (
        <RailSourceCard
          evidenceLabel={evidenceLabel}
          index={index}
          key={source.url}
          source={source}
        />
      ))}
    </div>
  );
}

export function MobileSourcesModal({
  evidenceLabel,
  isOpen,
  onOpenChange,
  sources,
  view,
}: {
  evidenceLabel: (source: SourceItem) => string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  sources: SourceItem[];
  view: "empty" | "run" | "report" | "failed";
}) {
  const { t } = useI18n();
  return (
    <Modal isOpen={isOpen} onOpenChange={onOpenChange}>
      <Button className="rail-btn" size="sm" variant="ghost">
        {t.wb.sourcesBtn}
      </Button>
      <Modal.Backdrop variant="blur">
        <Modal.Container placement="bottom" size="full">
          <Modal.Dialog className="source-modal">
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Heading>{t.wb.railTitle}</Modal.Heading>
            </Modal.Header>
            <Modal.Body>
              <SourceList
                emptyMessage={view === "run" ? t.wb.railEmptySearching : t.wb.railEmptyNone}
                evidenceLabel={evidenceLabel}
                sources={sources}
              />
            </Modal.Body>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}

export function SourcesRail({
  evidenceLabel,
  isRunning,
  sources,
  view,
}: {
  evidenceLabel: (source: SourceItem) => string;
  isRunning: boolean;
  sources: SourceItem[];
  view: "empty" | "run" | "report" | "failed";
}) {
  const { t } = useI18n();
  return (
    <aside className="rail">
      <div className="rail-head">
        <h2>{t.wb.railTitle}</h2>
        <span className="count">
          {sources.length ? `${sources.length} ${isRunning ? t.wb.railReading : t.wb.railSelected}` : ""}
        </span>
      </div>
      <div className="rail-scroll">
        {sources.length === 0 ? (
          <p className="rail-empty">
            {view === "run"
              ? t.wb.railEmptySearching
              : view === "failed"
                ? t.wb.railEmptyNone
                : t.wb.railEmptyIdle}
          </p>
        ) : (
          sources.map((source, index) => (
            <RailSourceCard
              evidenceLabel={evidenceLabel}
              index={index}
              key={source.url}
              source={source}
            />
          ))
        )}
      </div>
    </aside>
  );
}
