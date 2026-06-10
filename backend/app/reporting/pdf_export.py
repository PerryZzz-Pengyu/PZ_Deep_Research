from __future__ import annotations

import asyncio
from html import escape
import re
import unicodedata

from markdown_it import MarkdownIt
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.agent.schemas import ResearchJob


MAX_REPORT_CHARACTERS = 250_000
MODE_LABELS = {
    "quick": "快速研究",
    "deep": "深度研究",
    "expert": "专家研究",
}


class PdfExportError(RuntimeError):
    pass


def pdf_export_filename(query: str, job_id: str = "") -> str:
    normalized = unicodedata.normalize("NFKC", query).strip()
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", normalized)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    normalized = normalized.strip(".- ")
    normalized = normalized[:60].rstrip(".- ")
    fallback = f"pz-deep-research-{job_id[:8] or 'report'}"
    return f"{normalized or fallback}.pdf"


def _markdown_renderer() -> MarkdownIt:
    renderer = MarkdownIt(
        "commonmark",
        {
            "html": False,
            "linkify": False,
            "typographer": False,
        },
    )
    renderer.enable("table")
    renderer.enable("strikethrough")
    renderer.disable("image")
    return renderer


def build_pdf_document(job: ResearchJob, report: str) -> str:
    if len(report) > MAX_REPORT_CHARACTERS:
        raise PdfExportError("报告内容过长，无法导出 PDF")

    report_html = _markdown_renderer().render(report)
    title = escape(job.query)
    job_id = escape(job.id)
    mode = escape(MODE_LABELS.get(job.mode, job.mode))
    provider = escape(job.provider)
    model = escape(job.model or job.provider)
    created_at = job.created_at.strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    @page {{
      size: A4;
      margin: 20mm 18mm 22mm;
    }}
    * {{
      box-sizing: border-box;
    }}
    html {{
      color: #182027;
      background: #ffffff;
      font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
        "Noto Sans CJK SC", Arial, sans-serif;
      font-size: 10.5pt;
    }}
    body {{
      margin: 0;
      line-height: 1.7;
    }}
    .document-header {{
      margin: 0 0 11mm;
      padding: 0 0 7mm;
      border-bottom: 1.5px solid #1d8f80;
    }}
    .brand {{
      margin-bottom: 4mm;
      color: #13796d;
      font-size: 9pt;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    .document-title {{
      margin: 0 0 5mm;
      color: #101820;
      font-size: 22pt;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .metadata {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 2mm 8mm;
      margin: 0;
      color: #5c6770;
      font-size: 8.5pt;
    }}
    .metadata div {{
      display: grid;
      grid-template-columns: 18mm 1fr;
      gap: 2mm;
    }}
    .metadata dt {{
      font-weight: 700;
    }}
    .metadata dd {{
      min-width: 0;
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .report {{
      orphans: 3;
      widows: 3;
    }}
    h1, h2, h3, h4 {{
      break-after: avoid-page;
      color: #14232b;
      line-height: 1.35;
    }}
    h1 {{
      margin: 9mm 0 4mm;
      font-size: 18pt;
    }}
    h2 {{
      margin: 8mm 0 3mm;
      padding-bottom: 1.5mm;
      border-bottom: 1px solid #d6dddf;
      font-size: 14.5pt;
    }}
    h3 {{
      margin: 6mm 0 2.5mm;
      font-size: 12pt;
    }}
    h4 {{
      margin: 5mm 0 2mm;
      font-size: 10.5pt;
    }}
    p, ul, ol, blockquote, table, pre {{
      margin: 0 0 4mm;
    }}
    ul, ol {{
      padding-left: 6mm;
    }}
    li {{
      margin-bottom: 1.2mm;
    }}
    a {{
      color: #126f64;
      text-decoration: none;
      overflow-wrap: anywhere;
    }}
    blockquote {{
      padding: 3mm 4mm;
      border-left: 3px solid #6eaaa2;
      background: #f3f7f6;
      color: #435159;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      break-inside: avoid-page;
      font-size: 9pt;
    }}
    th, td {{
      padding: 2.2mm 2.5mm;
      border: 1px solid #ccd5d8;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      background: #edf4f2;
      font-weight: 700;
    }}
    code {{
      padding: 0.2mm 1mm;
      border-radius: 2px;
      background: #eef1f2;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 8.8pt;
    }}
    pre {{
      padding: 3mm;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
      background: #eef1f2;
    }}
    pre code {{
      padding: 0;
      background: transparent;
    }}
    hr {{
      margin: 7mm 0;
      border: 0;
      border-top: 1px solid #ccd5d8;
    }}
  </style>
</head>
<body>
  <header class="document-header">
    <div class="brand">PZ Deep Research</div>
    <h1 class="document-title">{title}</h1>
    <dl class="metadata">
      <div><dt>研究模式</dt><dd>{mode}</dd></div>
      <div><dt>模型</dt><dd>{provider} / {model}</dd></div>
      <div><dt>生成时间</dt><dd>{created_at}</dd></div>
      <div><dt>任务 ID</dt><dd>{job_id}</dd></div>
    </dl>
  </header>
  <main class="report">{report_html}</main>
</body>
</html>"""


class PdfExporter:
    def __init__(
        self,
        *,
        timeout_seconds: float = 45,
        max_concurrency: int = 2,
        chromium_executable_path: str = "",
    ) -> None:
        self.timeout_seconds = max(timeout_seconds, 1)
        self.chromium_executable_path = chromium_executable_path or None
        self._semaphore = asyncio.Semaphore(max(max_concurrency, 1))

    async def render(self, job: ResearchJob, report: str) -> bytes:
        document = build_pdf_document(job, report)
        async with self._semaphore:
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    return await self._render_document(job, document)
            except (TimeoutError, PlaywrightError, OSError) as exc:
                raise PdfExportError(str(exc)) from exc

    async def _render_document(self, job: ResearchJob, document: str) -> bytes:
        launch_options: dict[str, object] = {
            "headless": True,
            "args": ["--disable-dev-shm-usage", "--no-sandbox"],
        }
        if self.chromium_executable_path:
            launch_options["executable_path"] = self.chromium_executable_path

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**launch_options)
            try:
                context = await browser.new_context()

                async def block_network(route) -> None:
                    await route.abort()

                await context.route("**/*", block_network)
                page = await context.new_page()
                page.set_default_timeout(self.timeout_seconds * 1000)
                await page.set_content(document, wait_until="domcontentloaded")
                await page.emulate_media(media="print")
                return await page.pdf(
                    format="A4",
                    print_background=True,
                    display_header_footer=True,
                    header_template="<div></div>",
                    footer_template=(
                        '<div style="width:100%;padding:0 18mm;color:#778188;'
                        'font-size:8px;text-align:right;">'
                        f'{escape(job.query[:80])} · '
                        '<span class="pageNumber"></span> / <span class="totalPages"></span>'
                        "</div>"
                    ),
                    margin={
                        "top": "20mm",
                        "right": "18mm",
                        "bottom": "22mm",
                        "left": "18mm",
                    },
                    prefer_css_page_size=True,
                )
            finally:
                await browser.close()
