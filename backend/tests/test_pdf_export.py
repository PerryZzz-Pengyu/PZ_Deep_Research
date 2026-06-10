from __future__ import annotations

import asyncio

from app.agent.schemas import ResearchJob
from app.reporting.pdf_export import PdfExporter, build_pdf_document, pdf_export_filename


def test_pdf_export_filename_preserves_chinese_and_removes_unsafe_characters() -> None:
    assert pdf_export_filename("  PDF 导出 / 文件名:*?  ", "abcdef123456") == "PDF-导出-文件名.pdf"
    assert pdf_export_filename(" /:*? ", "abcdef123456") == "pz-deep-research-abcdef12.pdf"


def test_build_pdf_document_renders_markdown_without_executable_html() -> None:
    job = ResearchJob(
        id="abc123",
        query="测试 PDF 文档",
        mode="deep",
        provider="mock",
        model="mock",
        status="completed",
    )

    document = build_pdf_document(
        job,
        "# 标题\n\n<script>alert('x')</script>\n\n| A | B |\n| - | - |\n| 1 | 2 |",
    )

    assert "<h1>标题</h1>" in document
    assert "<table>" in document
    assert "<script>" not in document
    assert "&lt;script&gt;" in document
    assert "测试 PDF 文档" in document
    assert "abc123" in document


def test_pdf_exporter_generates_valid_pdf_with_installed_chromium() -> None:
    job = ResearchJob(
        id="pdf123",
        query="真实 Chromium PDF 生成验证",
        mode="quick",
        provider="mock",
        model="mock",
        status="completed",
    )
    exporter = PdfExporter(timeout_seconds=30, max_concurrency=1)

    pdf = asyncio.run(
        exporter.render(
            job,
            "# 核心结论\n\n这是包含中文内容的 PDF 报告。\n\n## References\n\n示例来源。",
        )
    )

    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf[-1024:]
    assert len(pdf) > 8_000
