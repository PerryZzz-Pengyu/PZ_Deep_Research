"use client";

import { Card, Tooltip } from "@heroui/react";
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

export type SourceItem = {
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

export function parseSources(rawSources: unknown): SourceItem[] {
  if (!Array.isArray(rawSources)) return [];
  return rawSources.flatMap((source, index) => {
    if (!source || typeof source !== "object") return [];
    const value = source as Record<string, unknown>;
    if (typeof value.url !== "string") return [];
    return [{
      citationId:
        typeof value.citation_id === "string"
          ? value.citation_id
          : typeof value.search_id === "string"
            ? value.search_id
            : String(index + 1),
      searchId: typeof value.search_id === "string" ? value.search_id : undefined,
      sourceKind: typeof value.source_kind === "string" ? value.source_kind : undefined,
      title: typeof value.title === "string" ? value.title : value.url,
      url: value.url,
      snippet: typeof value.snippet === "string" ? value.snippet : undefined,
      query: typeof value.query === "string" ? value.query : undefined,
      readStatus: typeof value.read_status === "string" ? value.read_status : undefined,
      evidenceLevel: typeof value.evidence_level === "string" ? value.evidence_level : undefined,
      evidenceNote: typeof value.evidence_note === "string" ? value.evidence_note : undefined,
      contentPreview: typeof value.content_preview === "string" ? value.content_preview : undefined,
    }];
  });
}

export function isVisitedSource(source: SourceItem) {
  if (source.sourceKind === "visited_source") return true;
  return /^\d+$/.test(source.citationId) && source.readStatus !== "search_result";
}

export function faviconUrl(url: string) {
  try {
    return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=32`;
  } catch {
    return "";
  }
}

export function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function formatApaReference(source: SourceItem) {
  return `${source.title}. (n.d.). Retrieved from ${source.url}`;
}

export function evidenceClass(source: SourceItem) {
  const value = source.evidenceLevel || source.readStatus;
  if (value === "full_text") return "strong";
  if (value === "partial_text") return "medium";
  if (value === "metadata" || value === "metadata_only") return "limited";
  return "muted";
}

export function markdownWithCitationLinks(report: string, sourceByCitation: Map<string, SourceItem>) {
  return report.replace(/\[(\d+)\](?!\()/g, (match, citationId: string) => {
    const source = sourceByCitation.get(citationId);
    return source ? `[[${citationId}]](${source.url})` : match;
  });
}

export function nodeText(node: unknown): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  return "";
}

export function CitationLink({
  children,
  evidenceLabel,
  href,
  source,
}: {
  children: ReactNode;
  evidenceLabel: (source: SourceItem) => string;
  href?: string;
  source?: SourceItem;
}) {
  const text = nodeText(children);
  if (!source) {
    return (
      <a href={href} rel="noreferrer" target="_blank">
        {children}
      </a>
    );
  }

  const icon = faviconUrl(source.url);
  return (
    <Tooltip delay={100}>
      <Tooltip.Trigger
        className="citation-wrap"
        render={(props) => <span {...props} />}
      >
        <sup className="citation-mark">{text}</sup>
      </Tooltip.Trigger>
      <Tooltip.Content className="citation-popover" placement="top" showArrow>
        <span className="source-topline">
          <span className="source-favicon" style={icon ? { backgroundImage: `url(${icon})` } : undefined} />
          <span className="source-citation">[{source.citationId}]</span>
          <span className="source-domain">{hostname(source.url)}</span>
        </span>
        <strong>{source.title}</strong>
        <span className={`evidence-badge ${evidenceClass(source)}`}>{evidenceLabel(source)}</span>
        {source.evidenceNote ? <small>{source.evidenceNote}</small> : null}
        <span className="source-url">{source.url}</span>
      </Tooltip.Content>
    </Tooltip>
  );
}

export function SourceCardItem({
  evidenceLabel,
  source,
}: {
  evidenceLabel: (source: SourceItem) => string;
  source: SourceItem;
}) {
  const icon = faviconUrl(source.url);
  return (
    <a href={source.url} rel="noreferrer" target="_blank">
      <Card className="wb-source-card" variant="secondary">
        <div className="source-topline">
          <span className="source-favicon" style={icon ? { backgroundImage: `url(${icon})` } : undefined} />
          <span className="source-citation">[{source.citationId}]</span>
          <span className="source-domain">{hostname(source.url)}</span>
          <span className={`evidence-badge ${evidenceClass(source)}`}>{evidenceLabel(source)}</span>
          <ExternalLink size={12} />
        </div>
        <strong>{source.title}</strong>
        {source.snippet ? <small>{source.snippet}</small> : null}
        <span className="source-url">{source.url}</span>
      </Card>
    </a>
  );
}

export function RailSourceCard({
  evidenceLabel,
  index,
  source,
}: {
  evidenceLabel: (source: SourceItem) => string;
  index: number;
  source: SourceItem;
}) {
  return (
    <a href={source.url} rel="noreferrer" target="_blank">
      <Card className="src-card" variant="secondary">
        <span className="num">[{index + 1}]</span>
        <div>
          <h3>{source.title}</h3>
          <p className="s-meta">{hostname(source.url)}</p>
          <span className={`strength ${evidenceClass(source) === "strong" ? "" : "mod"}`}>
            {evidenceLabel(source)}
          </span>
        </div>
      </Card>
    </a>
  );
}
