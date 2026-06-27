"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Locale = "zh" | "en";

const LOCALE_STORAGE_KEY = "pz-deep-research-locale";

/* ============================================================
   Dictionary — Chinese is the source of truth; English mirrors
   its shape so both locales stay structurally in sync.
   ============================================================ */

const zh = {
  brand: "PZ Deep Research",
  tagline: "深度研究工作台",
  langName: "中文",

  nav: {
    fields: "研究领域",
    how: "工作原理",
    modes: "研究模式",
    report: "研究报告",
    faq: "常见问题",
    signIn: "登录",
    start: "开始研究",
  },

  home: {
    heroChip: "学术研究已上线 · 更多领域陆续开放",
    heroTitleA: "深度研究，",
    heroTitleB: "每条结论都有出处",
    heroSub:
      "提出一个问题。PZ Deep Research 会检索实时网络、阅读来源、抽取证据，并撰写一份带编号引用、可供你逐条核验的结构化研究报告。",
    askPlaceholder:
      "输入一个研究问题 —— 例如：固态电池与锂离子电池在成本和安全性上如何对比？",
    startResearch: "开始研究",
    modeHints: {
      quick: "快速 · 1 次检索 · 3 个引用来源 · 约 500 字简报",
      deep: "深度 · 3 次检索 · 10 个引用来源 · 约 1,500 字综述",
      expert: "专家 · 2 轮检索 · 20 个引用来源 · 约 3,500 字报告",
    },
    trust: ["免费起步，无需信用卡", "基于真实来源，绝非凭记忆作答", "支持导出 Markdown 与 PDF"],

    fieldsKicker: "研究领域",
    fieldsTitle: "一套引擎，覆盖多个研究领域",
    fieldsSub:
      "PZ Deep Research 把深度研究拆分为多个专属领域，每个领域有自己的来源、检索策略与报告格式。学术领域现已上线，其余领域正在陆续点亮。",
    fields: [
      { name: "学术", desc: "来自论文、期刊与学术搜索的文献综述。", live: true },
      { name: "金融", desc: "公司研究、财报披露、市场数据与业绩分析。", live: false },
      { name: "行业分析", desc: "竞争格局、市场规模与赛道深度剖析。", live: false },
      { name: "法律", desc: "判例、法条与监管研究，引用精确。", live: false },
      { name: "能源", desc: "政策、电网数据与能源转型技术评估。", live: false },
      { name: "生物技术", desc: "机制、管线与预印本感知的生命科学研究。", live: false },
      { name: "医药", desc: "临床试验、药物审批与证据分级的医学来源。", live: false },
      { name: "社交媒体", desc: "公开社交平台上的趋势与情绪研究。", live: false },
    ],

    howKicker: "方法论",
    howTitle: "真正的研究流水线，而非更长的提示词",
    howSub:
      "每一份报告都跑同一条证据优先的流水线。你可以实时观看每一步，并随时取消。",
    steps: [
      { t: "理解", d: "将你的问题解析为研究意图与高召回检索词。" },
      { t: "检索", d: "实时网络与学术检索 —— 按模式执行 1 到 10 次查询。" },
      { t: "阅读", d: "打开真实页面，阅读完整正文，而非片段摘要。" },
      { t: "抽取证据", d: "把可引用的事实抽取为证据卡片，并按强度分级。" },
      { t: "撰写", d: "结构化、带引用的报告 —— 结论、分析、来源与告诫。" },
    ],

    modesKicker: "研究深度",
    modesTitle: "三种深度，同一条诚实的流水线",
    modesSub:
      "快速、深度与专家不是三种不同的产品 —— 它们是同一条流水线在不同强度下运行。由你决定挖得多深。",
    modeCards: [
      {
        kicker: "快速",
        title: "带出处的简报",
        desc: "当你需要一个可靠、有依据且快速的答案时。",
        stats: [
          ["检索次数", "1"],
          ["引用来源", "3"],
          ["报告长度", "约 500 字"],
          ["典型耗时", "约 2 分钟"],
        ],
        cta: "运行快速简报",
        primary: false,
      },
      {
        kicker: "深度",
        title: "一篇文献综述",
        desc: "面向严肃问题的默认选择 —— 广泛检索、强力来源、结构化分析。",
        stats: [
          ["检索次数", "3"],
          ["引用来源", "10"],
          ["报告长度", "约 1,500 字"],
          ["典型耗时", "约 6 分钟"],
        ],
        cta: "运行深度研究",
        primary: true,
      },
      {
        kicker: "专家",
        title: "论文级报告",
        desc: "两轮检索之间插入缺口复查 —— 面向真正重要的决策。",
        stats: [
          ["检索轮次", "2 × 5 次"],
          ["引用来源", "20"],
          ["报告长度", "约 3,500 字"],
          ["典型耗时", "约 15 分钟"],
        ],
        cta: "运行专家研究",
        primary: false,
      },
    ],

    reportKicker: "成果产出",
    reportTitle: "可以直接交付他人的研究报告",
    reportSub:
      "核心结论前置，分析全程关联证据，来源在文末编号 —— 并明确标注仍存不确定之处。",
    reportDocMeta: ["深度 · 10 个来源", "学术"],
    reportDocTitle: "固态电池 vs. 锂离子电池：成本与安全展望",
    reportH1: "核心结论",
    reportP1a:
      "固态电池单位 kWh 成本目前约为成熟锂离子量产的 4–8 倍，主要源于固态电解质加工与较低的制造良率",
    reportP1b: "。多数同行评审路线图认为成本平价不会早于 2030 年，且仅限于部分细分场景",
    reportH2: "安全特性",
    reportP2a:
      "移除易燃液态电解质消除了主要的热失控路径，但在硫化物体系中，快充下的枝晶生长仍是尚未解决的失效模式",
    reportP2b: "。各来源在汽车温区下的循环寿命上存在分歧 —— 已在下文标注为未解决的争议",
    reportSources: [
      { title: "规模化硫化物固态电池制造的成本建模", domain: "nature.com · Nature Energy · 2025" },
      { title: "2030 电池技术路线图：电解质路径对比", domain: "sciencedirect.com · Joule · 2025" },
      { title: "氧化物电解质生产中的良率瓶颈", domain: "acs.org · ACS Energy Letters · 2024" },
      { title: "高电流密度下的枝晶抑制策略", domain: "science.org · Science · 2025" },
    ],

    faqKicker: "常见问题",
    faqTitle: "你关心的问题，这里都有答案",
    faq: [
      {
        q: "什么是 PZ Deep Research 深度研究？",
        a: "它是一个为每个问题运行真实研究流水线的 AI 研究助手：检索实时网络、打开并阅读来源、抽取证据，并撰写带编号引用的结构化报告，让每条论断都能追溯到出处。",
      },
      {
        q: "它和聊天机器人有什么不同？",
        a: "聊天机器人凭记忆作答，而它从证据出发 —— 总是先检索、阅读真实来源页面、把来源证据与模型推断区分开，并在来源相互冲突时明确指出，而非掩盖。",
      },
      {
        q: "每份报告都包含来源和引用吗？",
        a: "是的。根据研究模式，它会挑选 3、10 或 20 个最强来源，为其编号并在全文中行内引用，附完整参考文献列表，并明确标注不确定之处。",
      },
      {
        q: "它覆盖哪些研究领域？",
        a: "学术 —— 学术与科研研究 —— 现已上线。金融、行业分析、法律、生物技术、医药、能源和社交媒体研究正在作为各自独立的领域开发中，拥有专属的来源与报告格式。",
      },
      {
        q: "我可以导出研究报告吗？",
        a: "每份完成的报告都可导出为 Markdown 文件或分页的 A4 PDF，引用与参考文献会原样保留。",
      },
      {
        q: "使用是免费的吗？",
        a: "无需账号即可免费开始研究。登录后可在多设备间同步研究历史 —— 首次登录时，你的访客历史会自动并入账号。",
      },
    ],

    ctaTitleA: "你的下一个问题，值得",
    ctaTitleB: "一次真正的研究",
    ctaSub: "在工作台免费起步 —— 无需账号。你的第一份带引用报告，几分钟即可生成。",
    ctaBtn: "打开工作台",

    footerTagline: "AI 深度研究助手。检索、阅读、核验、引用 —— 覆盖每一个你关心的领域。",
    footerProduct: "产品",
    footerProductLinks: ["研究工作台", "研究模式", "带引用报告", "方法论"],
    footerFields: "领域",
    footerFieldsLinks: ["学术研究", "金融研究", "法律研究", "生物技术研究"],
    footerResources: "资源",
    footerResourcesLinks: ["常见问题", "工作原理", "示例报告", "更新日志"],
    footerCompany: "公司",
    footerCompanyLinks: ["关于", "隐私", "条款", "联系"],
    footerCopyright: "© 2026 PZ Deep Research",
    footerSlogan: "证据优先，永远有出处。",
  },

  modes: { quick: "快速", deep: "深度", expert: "专家" },
  modeDetails: { quick: "3 源短文", deep: "10 源综述", expert: "20 源论文" },

  providers: { mock: "开发模式", openai: "OpenAI", anthropic: "Claude", gemini: "Gemini" },

  wb: {
    newResearch: "新建研究",
    fieldsLabel: "研究领域",
    field: { scholar: "学术", finance: "金融", legal: "法律", biotech: "生物技术" },
    soon: "敬请期待",
    historyLabel: "历史记录",
    crumbRoot: "学术",
    crumbNew: "新建研究",
    crumbResearching: "研究中…",
    sourcesBtn: "来源",
    openMenu: "打开菜单",

    emptyTitle: "想研究点什么？",
    emptySub: "证据优先的答案 —— 检索、阅读、核验、引用。",
    askPlaceholder: "输入一个研究问题 —— 系统会检索、阅读来源并撰写带引用的报告",
    advanced: "高级选项",
    byokLabel: "API Key（自带）",
    byokPlaceholder: "粘贴你的 API Key —— 仅本次请求使用，不会保存",
    byokHint: "可选。留空则使用服务端配置的 Key。",
    searchKeyLabel: "SerpAPI Key（自带）",
    searchKeyPlaceholder: "用于本次真实学术检索",
    searchKeyHint: "可选。填写后本次任务使用 SerpAPI，不写入浏览器或数据库。",
    readerKeyLabel: "Jina Key（自带）",
    readerKeyPlaceholder: "用于本次网页正文读取",
    readerKeyHint: "可选。无 Key 也可读取，填写后使用你的 Jina 额度。",
    requestCredentialsTitle: "本次重跑凭据",
    requestCredentialsHint: "BYOK 凭据不会保存。重新运行或重试真实模型任务前请再次填写。",
    advScope: "来源范围",
    advScopeOptions: ["学术 —— 论文与期刊", "全网"],
    advTime: "时间范围",
    advTimeOptions: ["任意时间", "近 5 年", "近 1 年"],
    advFormat: "报告格式",
    advFormatOptions: ["文献综述", "简报", "利弊对比"],
    recentTitle: "最近的研究",
    recentEmpty: "还没有研究记录。提出第一个问题即可开始。",

    runLabelSuffix: "研究 · 学术",
    running: "运行中",
    sourcesTarget: "个来源（目标）",
    cancel: "取消研究",
    thinking: "正在深度思考…",
    liveOutput: "模型实时输出",

    reportLabelSuffix: "研究 · 学术 · 最终报告",
    sourcesCited: "个引用来源",
    words: "字",
    elapsed: "耗时",
    exportMd: "导出 Markdown",
    exportPdf: "导出 PDF",
    rerun: "重新运行",
    rerunning: "正在创建",
    references: "参考文献",
    reportPlaceholder: "报告将在研究完成后显示。",

    failTitle: "研究服务繁忙",
    failBody:
      "由于服务负载过高，本次任务未能完成。你的问题与设置已保存 —— 重试会从证据中断处继续。",
    retry: "重试研究",
    retrying: "正在重试",

    railTitle: "来源",
    railSelected: "个已选",
    railReading: "个阅读中",
    railEmptyIdle: "研究开始后，为报告选定的来源会显示在这里。",
    railEmptySearching: "正在检索候选来源…",
    railEmptyNone: "暂无来源 —— 本次任务未完成。",

    stop: "停止",
    stopping: "正在停止",
    start: "开始",
    restoring: "正在恢复",
    backToHistory: "返回历史",

    accountSignIn: "登录并同步历史",
    accountReading: "正在读取账号",
    accountSignedInDesc: "历史已绑定账号",
    accountGuest: "访客模式",
    accountGuestDesc: "历史保存在当前浏览器",
    syncedAcross: "已跨设备同步",

    cancelled: "研究已取消",
    reportReady: "报告已就绪 —— 已引用",
    mdExported: "已导出 Markdown",

    progressTitle: "研究进度",
    waitingStart: "等待任务开始",
    noLog: "暂无研究日志",
  },

  status: {
    queued: "等待开始",
    running: "研究中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    idle: "尚未创建",
  },

  errors: {
    createFailed: "暂时无法创建研究任务。",
    cancelFailed: "取消研究任务失败",
    rerunFailed: "重新运行研究任务失败",
    retryFailed: "暂时无法重试研究任务。",
    pdfFailed: "导出 PDF 失败",
    historyFailed: "获取研究历史失败",
    detailFailed: "打开报告详情失败",
    networkUnstable: "网络连接不稳定，正在自动恢复研究进度。",
    connectionLost: "连接暂时中断，请刷新页面恢复任务。",
  },
};

type Dict = typeof zh;

const en: Dict = {
  brand: "PZ Deep Research",
  tagline: "Research workbench",
  langName: "English",

  nav: {
    fields: "Fields",
    how: "How it works",
    modes: "Modes",
    report: "Reports",
    faq: "FAQ",
    signIn: "Sign in",
    start: "Start researching",
  },

  home: {
    heroChip: "Scholar research is live · more fields coming",
    heroTitleA: "Deep research, ",
    heroTitleB: "with every claim cited",
    heroSub:
      "Ask one question. PZ Deep Research searches the live web, reads the sources, extracts the evidence, and writes a structured research report — with numbered citations you can verify yourself.",
    askPlaceholder:
      "Ask a research question — e.g. How do solid-state batteries compare to lithium-ion on cost and safety?",
    startResearch: "Start research",
    modeHints: {
      quick: "quick · 1 search query · 3 cited sources · ~500-word brief",
      deep: "deep · 3 search queries · 10 cited sources · ~1,500-word review",
      expert: "expert · 2 search passes · 20 cited sources · ~3,500-word report",
    },
    trust: ["Free to start, no card required", "Real sources, never just memory", "Export to Markdown & PDF"],

    fieldsKicker: "Research fields",
    fieldsTitle: "One engine, a spectrum of fields",
    fieldsSub:
      "PZ Deep Research splits deep research into dedicated fields — each with its own sources, search strategy and report format. Scholar is live today; the rest of the spectrum is lighting up.",
    fields: [
      { name: "Scholar", desc: "Academic literature reviews from papers, journals and scholar sources.", live: true },
      { name: "Finance", desc: "Company research, filings, market data and earnings analysis.", live: false },
      { name: "Industry analysis", desc: "Competitive landscapes, market sizing and sector deep dives.", live: false },
      { name: "Legal", desc: "Case law, statutes and regulatory research with precise citations.", live: false },
      { name: "Energy", desc: "Policy, grid data and technology assessments across the transition.", live: false },
      { name: "Biotech", desc: "Mechanisms, pipelines and preprint-aware life-science research.", live: false },
      { name: "Pharma", desc: "Clinical trials, drug approvals and evidence-graded medical sources.", live: false },
      { name: "Social media", desc: "Trend and sentiment research across public social platforms.", live: false },
    ],

    howKicker: "Methodology",
    howTitle: "A real research pipeline, not a longer prompt",
    howSub:
      "Every report runs the same evidence-first pipeline. You watch each step happen live — and you can cancel any time.",
    steps: [
      { t: "Understand", d: "Your question is parsed into research intent and high-recall search queries." },
      { t: "Search", d: "Live web and scholar search — 1 to 10 queries depending on mode." },
      { t: "Read", d: "It opens the actual pages and reads full source content, not snippets." },
      { t: "Extract evidence", d: "Citable facts are pulled into evidence cards, graded by strength." },
      { t: "Write", d: "A structured, cited report — conclusions, analysis, sources, caveats." },
    ],

    modesKicker: "Research depth",
    modesTitle: "Three depths, one honest pipeline",
    modesSub:
      "Quick, Deep and Expert aren't different products — they're the same pipeline at different intensities. Pick how far you want to dig.",
    modeCards: [
      {
        kicker: "Quick",
        title: "A sourced brief",
        desc: "For when you need a reliable answer with receipts, fast.",
        stats: [
          ["Search queries", "1"],
          ["Cited sources", "3"],
          ["Report length", "~500 words"],
          ["Typical time", "~2 min"],
        ],
        cta: "Run a quick brief",
        primary: false,
      },
      {
        kicker: "Deep",
        title: "A literature review",
        desc: "The default for serious questions — broad search, strong sources, structured analysis.",
        stats: [
          ["Search queries", "3"],
          ["Cited sources", "10"],
          ["Report length", "~1,500 words"],
          ["Typical time", "~6 min"],
        ],
        cta: "Run deep research",
        primary: true,
      },
      {
        kicker: "Expert",
        title: "A paper-grade report",
        desc: "Two search passes with a gap review in between — for decisions that matter.",
        stats: [
          ["Search passes", "2 × 5 queries"],
          ["Cited sources", "20"],
          ["Report length", "~3,500 words"],
          ["Typical time", "~15 min"],
        ],
        cta: "Run expert research",
        primary: false,
      },
    ],

    reportKicker: "The output",
    reportTitle: "Reports you can actually hand to someone",
    reportSub:
      "Core conclusions up front, evidence-linked analysis throughout, numbered sources at the end — and explicit notes on what remains uncertain.",
    reportDocMeta: ["Deep · 10 sources", "Scholar"],
    reportDocTitle: "Solid-state vs. lithium-ion batteries: cost and safety outlook",
    reportH1: "Core conclusions",
    reportP1a:
      "Solid-state cells currently cost an estimated 4–8× more per kWh than mature lithium-ion production, driven by solid-electrolyte processing and low yields",
    reportP1b: ". Most peer-reviewed roadmaps place cost parity no earlier than 2030 for limited segments",
    reportH2: "Safety profile",
    reportP2a:
      "Eliminating flammable liquid electrolytes removes the dominant thermal-runaway pathway, but dendrite formation under fast charging remains an open failure mode in sulfide systems",
    reportP2b: ". Sources conflict on cycle-life at automotive temperatures — flagged below as an unresolved disagreement",
    reportSources: [
      { title: "Cost modelling of sulfide solid-state cell manufacturing at scale", domain: "nature.com · Nature Energy · 2025" },
      { title: "Battery technology roadmap 2030: electrolyte pathways compared", domain: "sciencedirect.com · Joule · 2025" },
      { title: "Manufacturing yield barriers in oxide electrolyte production", domain: "acs.org · ACS Energy Letters · 2024" },
      { title: "Dendrite suppression strategies under high current density", domain: "science.org · Science · 2025" },
    ],

    faqKicker: "FAQ",
    faqTitle: "Questions, answered",
    faq: [
      {
        q: "What is PZ Deep Research?",
        a: "It is an AI research assistant that runs a real research pipeline for every question: it searches the live web, opens and reads the sources, extracts evidence, and writes a structured report with numbered citations linking every claim back to its source.",
      },
      {
        q: "How is it different from a chatbot?",
        a: "A chatbot answers from memory. This answers from evidence — it always searches first, reads the actual source pages, separates source evidence from model inference, and flags conflicts between sources instead of papering over them.",
      },
      {
        q: "Does every report include sources and citations?",
        a: "Yes. Depending on the research mode, it selects the 3, 10 or 20 strongest sources, numbers them, and cites them inline throughout the report. A full reference list is included, and uncertainty is called out explicitly.",
      },
      {
        q: "Which research fields does it cover?",
        a: "Scholar — academic and scientific research — is live today. Finance, industry analysis, legal, biotech, pharma, energy and social-media research are in development as dedicated fields with their own sources and report formats.",
      },
      {
        q: "Can I export my research reports?",
        a: "Every finished report can be exported as a Markdown file or a paginated A4 PDF, with citations and references preserved exactly as shown.",
      },
      {
        q: "Is it free to use?",
        a: "You can start researching for free, without an account. Sign in to keep your research history in sync across devices — your guest history is merged into your account automatically on first login.",
      },
    ],

    ctaTitleA: "Your next question deserves ",
    ctaTitleB: "real research",
    ctaSub: "Start free in the workbench — no account needed. Your first cited report is minutes away.",
    ctaBtn: "Open the workbench",

    footerTagline: "The AI deep research assistant. Searched, read, verified and cited — across every field that matters to you.",
    footerProduct: "Product",
    footerProductLinks: ["Research workbench", "Research modes", "Cited reports", "Methodology"],
    footerFields: "Fields",
    footerFieldsLinks: ["Scholar research", "Finance research", "Legal research", "Biotech research"],
    footerResources: "Resources",
    footerResourcesLinks: ["FAQ", "How it works", "Example report", "Changelog"],
    footerCompany: "Company",
    footerCompanyLinks: ["About", "Privacy", "Terms", "Contact"],
    footerCopyright: "© 2026 PZ Deep Research",
    footerSlogan: "Evidence first. Always cited.",
  },

  modes: { quick: "Quick", deep: "Deep", expert: "Expert" },
  modeDetails: { quick: "3 sources", deep: "10 sources", expert: "20 sources" },

  providers: { mock: "Dev mode", openai: "OpenAI", anthropic: "Claude", gemini: "Gemini" },

  wb: {
    newResearch: "New research",
    fieldsLabel: "Fields",
    field: { scholar: "Scholar", finance: "Finance", legal: "Legal", biotech: "Biotech" },
    soon: "SOON",
    historyLabel: "History",
    crumbRoot: "Scholar",
    crumbNew: "New research",
    crumbResearching: "Researching…",
    sourcesBtn: "Sources",
    openMenu: "Open menu",

    emptyTitle: "What should we research?",
    emptySub: "Evidence-first answers — searched, read, verified and cited.",
    askPlaceholder: "Ask a research question — it will search, read the sources and write a cited report",
    advanced: "Advanced options",
    byokLabel: "API key (bring your own)",
    byokPlaceholder: "Paste your API key — used only for this request, never stored",
    byokHint: "Optional. Leave empty to use the server-configured key.",
    searchKeyLabel: "SerpAPI key (BYOK)",
    searchKeyPlaceholder: "Used for this request's live scholar search",
    searchKeyHint: "Optional. This request uses SerpAPI without saving the key.",
    readerKeyLabel: "Jina key (BYOK)",
    readerKeyPlaceholder: "Used for this request's webpage retrieval",
    readerKeyHint: "Optional. Retrieval works without a key; add yours for your Jina quota.",
    requestCredentialsTitle: "Credentials for this run",
    requestCredentialsHint: "BYOK credentials are never saved. Enter them again before re-running or retrying a real-provider task.",
    advScope: "Source scope",
    advScopeOptions: ["Scholar — papers & journals", "Whole web"],
    advTime: "Time range",
    advTimeOptions: ["Any time", "Last 5 years", "Last year"],
    advFormat: "Report format",
    advFormatOptions: ["Literature review", "Brief", "Pros & cons"],
    recentTitle: "Recent research",
    recentEmpty: "No research yet. Ask your first question to begin.",

    runLabelSuffix: "research · Scholar",
    running: "Running",
    sourcesTarget: "sources target",
    cancel: "Cancel research",
    thinking: "Deep thinking…",
    liveOutput: "Live model output",

    reportLabelSuffix: "research · Scholar · final report",
    sourcesCited: "sources cited",
    words: "words",
    elapsed: "elapsed",
    exportMd: "Export Markdown",
    exportPdf: "Export PDF",
    rerun: "Re-run",
    rerunning: "Creating",
    references: "References",
    reportPlaceholder: "The report will appear here once research completes.",

    failTitle: "The research service was busy",
    failBody:
      "This task couldn't finish because the service was under heavy load. Your question and settings are saved — retrying will pick up where the evidence left off.",
    retry: "Retry research",
    retrying: "Retrying",

    railTitle: "Sources",
    railSelected: "selected",
    railReading: "reading",
    railEmptyIdle: "Sources selected for your report will appear here once research starts.",
    railEmptySearching: "Searching for candidate sources…",
    railEmptyNone: "No sources — this task did not complete.",

    stop: "Stop",
    stopping: "Stopping",
    start: "Start",
    restoring: "Restoring",
    backToHistory: "Back to history",

    accountSignIn: "Sign in to sync history",
    accountReading: "Loading account",
    accountSignedInDesc: "History linked to account",
    accountGuest: "Guest mode",
    accountGuestDesc: "History saved in this browser",
    syncedAcross: "Synced across devices",

    cancelled: "Research cancelled",
    reportReady: "Report ready — cited",
    mdExported: "Markdown exported",

    progressTitle: "Research progress",
    waitingStart: "Waiting to start",
    noLog: "No research log yet",
  },

  status: {
    queued: "Queued",
    running: "Researching",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
    idle: "Not created",
  },

  errors: {
    createFailed: "Unable to create a research task right now.",
    cancelFailed: "Failed to cancel the research task",
    rerunFailed: "Failed to re-run the research task",
    retryFailed: "Unable to retry the research task right now.",
    pdfFailed: "Failed to export PDF",
    historyFailed: "Failed to load research history",
    detailFailed: "Failed to open report detail",
    networkUnstable: "The connection is unstable; restoring research progress automatically.",
    connectionLost: "The connection dropped; please refresh the page to resume the task.",
  },
};

const dictionaries: Record<Locale, Dict> = { zh, en };

type I18nState = {
  locale: Locale;
  setLocale: (next: Locale) => void;
  toggleLocale: () => void;
  t: Dict;
};

const I18nContext = createContext<I18nState | null>(null);

function readInitialLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (stored === "zh" || stored === "en") return stored;
  return "zh";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");

  // Hydration-safe: SSR + first client render use "zh"; the persisted
  // preference is applied right after mount (client-only storage read).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocaleState(readInitialLocale());
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // ignore storage failures (private mode etc.)
    }
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === "zh" ? "en" : "zh");
  }, [locale, setLocale]);

  return (
    <I18nContext.Provider value={{ locale, setLocale, toggleLocale, t: dictionaries[locale] }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within <I18nProvider>");
  }
  return ctx;
}
