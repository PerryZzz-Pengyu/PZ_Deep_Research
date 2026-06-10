type MarkdownExportInput = {
  query: string;
  report: string;
  jobId?: string;
};

export function markdownExportFilename(query: string, jobId = "") {
  const normalized = query
    .normalize("NFKC")
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, " ")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[.\-\s]+|[.\-\s]+$/g, "")
    .slice(0, 60)
    .replace(/[.\-\s]+$/g, "");
  const fallback = `pz-deep-research-${jobId.slice(0, 8) || "report"}`;
  return `${normalized || fallback}.md`;
}

export function downloadMarkdownReport({ query, report, jobId }: MarkdownExportInput) {
  if (!report) return;

  const content = report.endsWith("\n") ? report : `${report}\n`;
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  downloadBlobFile(blob, markdownExportFilename(query, jobId));
}

export function downloadBlobFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
