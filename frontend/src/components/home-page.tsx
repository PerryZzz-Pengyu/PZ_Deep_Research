"use client";

import { Accordion, Button, Card, TextArea } from "@heroui/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type KeyboardEvent } from "react";

import { SignInControl } from "@/components/auth-controls";
import { BrandMark } from "@/components/brand-mark";
import { LanguageSwitch } from "@/components/language-switch";
import { ResearchModeTabs } from "@/components/research-mode-tabs";
import { writeHandoff } from "@/lib/handoff";
import { useI18n } from "@/lib/i18n";
import type { ResearchMode } from "@/lib/types";

const FIELD_GLYPHS = ["g-tri", "g-bars", "g-square", "g-line", "g-circle", "g-rings", "g-diamond", "g-dot"];
export function HomePage() {
  const { t } = useI18n();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ResearchMode>("deep");

  function go() {
    const trimmed = query.trim();
    if (trimmed) {
      writeHandoff({ query: trimmed, mode, autostart: true });
    }
    router.push("/workbench");
  }

  function onAskKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      go();
    }
  }

  return (
    <>
      <div className="atmosphere" aria-hidden="true" />

      <header className="site-nav glass">
        <Link className="brand" href="#top" aria-label={t.brand}>
          <BrandMark />
          <span>{t.brand}</span>
        </Link>
        <ul className="nav-links">
          <li><a href="#fields">{t.nav.fields}</a></li>
          <li><a href="#how">{t.nav.how}</a></li>
          <li><a href="#modes">{t.nav.modes}</a></li>
          <li><a href="#report">{t.nav.report}</a></li>
          <li><a href="#faq">{t.nav.faq}</a></li>
        </ul>
        <div className="nav-cta">
          <LanguageSwitch />
          <SignInControl />
          <Button className="nav-start" size="sm" variant="primary" onPress={() => router.push("/workbench")}>
            {t.nav.start}
          </Button>
        </div>
      </header>

      <main id="top">
        {/* HERO */}
        <section className="hero">
          <div className="dotgrid" aria-hidden="true" />
          <div className="wrap">
            <div className="hero-chip">
              <span className="chip"><span className="dot live" />{t.home.heroChip}</span>
            </div>
            <h1>
              {t.home.heroTitleA}
              <span className="spectrum-text">{t.home.heroTitleB}</span>
            </h1>
            <p className="hero-sub">{t.home.heroSub}</p>

            <Card className="hero-ask flow-ring" role="search" variant="secondary">
              <label className="sr-only" htmlFor="ask">{t.nav.start}</label>
              <TextArea
                id="ask"
                className="ask-input"
                rows={2}
                placeholder={t.home.askPlaceholder}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={onAskKeyDown}
                variant="secondary"
              />
              <div className="ask-controls">
                <ResearchModeTabs
                  ariaLabel={t.nav.modes}
                  labels={t.modes}
                  mode={mode}
                  onModeChange={setMode}
                />
                <Button className="ask-go" onPress={go} variant="primary">
                  {t.home.startResearch}
                </Button>
              </div>
            </Card>
            <p className="mode-hint">{t.home.modeHints[mode]}</p>

            <div className="trust-row">
              {t.home.trust.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </div>
        </section>

        {/* FIELDS */}
        <section className="section" id="fields">
          <div className="wrap">
            <div className="section-head">
              <p className="kicker">{t.home.fieldsKicker}</p>
              <h2>{t.home.fieldsTitle}</h2>
              <p>{t.home.fieldsSub}</p>
            </div>
            <div className="domain-grid">
              {t.home.fields.map((field, index) => {
                const inner = (
                  <>
                    <div className="domain-top">
                      <span className={`glyph ${FIELD_GLYPHS[index]}`}><i /></span>
                      {field.live ? (
                        <span className="chip"><span className="dot live" />Live</span>
                      ) : (
                        <span className="status-soon">{t.wb.soon}</span>
                      )}
                    </div>
                    <h3>{field.name}</h3>
                    <p>{field.desc}</p>
                  </>
                );
                return field.live ? (
                  <Link key={field.name} className="domain-link" href="/workbench">
                    <Card className="domain-card" variant="secondary">{inner}</Card>
                  </Link>
                ) : (
                  <Card key={field.name} className="domain-card" variant="secondary">{inner}</Card>
                );
              })}
            </div>
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="section" id="how">
          <div className="wrap">
            <div className="section-head">
              <p className="kicker">{t.home.howKicker}</p>
              <h2>{t.home.howTitle}</h2>
              <p>{t.home.howSub}</p>
            </div>
            <div className="pipeline">
              {t.home.steps.map((step, index) => (
                <div className="step" key={step.t}>
                  <div className="step-node glass">{String(index + 1).padStart(2, "0")}</div>
                  <h3>{step.t}</h3>
                  <p>{step.d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* MODES */}
        <section className="section" id="modes">
          <div className="wrap">
            <div className="section-head">
              <p className="kicker">{t.home.modesKicker}</p>
              <h2>{t.home.modesTitle}</h2>
              <p>{t.home.modesSub}</p>
            </div>
            <div className="mode-grid">
              {t.home.modeCards.map((card) => (
                <Card
                  className={card.primary ? "mode-card flow-ring" : "mode-card"}
                  key={card.kicker}
                  variant="secondary"
                >
                  <p className="kicker">{card.kicker}</p>
                  <h3>{card.title}</h3>
                  <p className="mode-desc">{card.desc}</p>
                  <ul className="mode-stats">
                    {card.stats.map(([label, value]) => (
                      <li key={label}>{label} <b>{value}</b></li>
                    ))}
                  </ul>
                  <Button
                    className="mode-cta"
                    variant={card.primary ? "primary" : "secondary"}
                    onPress={() => router.push("/workbench")}
                  >
                    {card.cta}
                  </Button>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* REPORT PREVIEW */}
        <section className="section" id="report">
          <div className="wrap">
            <div className="section-head">
              <p className="kicker">{t.home.reportKicker}</p>
              <h2>{t.home.reportTitle}</h2>
              <p>{t.home.reportSub}</p>
            </div>
            <div className="report-split">
              <Card className="report-doc" variant="secondary">
                <div className="doc-meta">
                  {t.home.reportDocMeta.map((meta) => (
                    <span className="chip" key={meta}>{meta}</span>
                  ))}
                </div>
                <h3>{t.home.reportDocTitle}</h3>
                <h4>{t.home.reportH1}</h4>
                <p>
                  {t.home.reportP1a}<span className="cite">[1]</span><span className="cite">[3]</span>
                  {t.home.reportP1b}<span className="cite">[2]</span>。
                </p>
                <h4>{t.home.reportH2}</h4>
                <p>
                  {t.home.reportP2a}<span className="cite">[4]</span><span className="cite">[7]</span>
                  {t.home.reportP2b}<span className="cite">[5]</span>。
                </p>
              </Card>
              <aside className="source-list" aria-label="Example sources">
                {t.home.reportSources.map((source, index) => (
                  <Card className="source-card" key={source.title} variant="secondary">
                    <span className="num">[{index + 1}]</span>
                    <div>
                      <h5>{source.title}</h5>
                      <p className="domain">{source.domain}</p>
                    </div>
                  </Card>
                ))}
              </aside>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="section" id="faq">
          <div className="wrap">
            <div className="section-head">
              <p className="kicker">{t.home.faqKicker}</p>
              <h2>{t.home.faqTitle}</h2>
            </div>
            <Accordion className="faq-list" defaultExpandedKeys={["faq-0"]} variant="surface">
              {t.home.faq.map((item, index) => (
                <Accordion.Item className="faq-item" id={`faq-${index}`} key={item.q}>
                  <Accordion.Heading>
                    <Accordion.Trigger className="faq-trigger">
                      {item.q}
                      <Accordion.Indicator className="faq-indicator" />
                    </Accordion.Trigger>
                  </Accordion.Heading>
                  <Accordion.Panel className="faq-panel">
                    <Accordion.Body className="faq-body">{item.a}</Accordion.Body>
                  </Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          </div>
        </section>

        {/* CTA */}
        <section className="section">
          <div className="wrap">
            <Card className="cta-band flow-ring" variant="secondary">
              <h2>{t.home.ctaTitleA}<span className="spectrum-text">{t.home.ctaTitleB}</span></h2>
              <p>{t.home.ctaSub}</p>
              <Button className="cta-button" variant="primary" onPress={() => router.push("/workbench")}>
                {t.home.ctaBtn}
              </Button>
            </Card>
          </div>
        </section>
      </main>

      <footer className="site-footer hairline-top">
        <div className="wrap">
          <div className="footer-grid">
            <div className="footer-brand">
              <Link className="brand" href="#top">
                <BrandMark />
                <span>{t.brand}</span>
              </Link>
              <p>{t.home.footerTagline}</p>
            </div>
            <nav aria-label={t.home.footerProduct}>
              <h4>{t.home.footerProduct}</h4>
              <ul>
                <li><Link href="/workbench">{t.home.footerProductLinks[0]}</Link></li>
                <li><a href="#modes">{t.home.footerProductLinks[1]}</a></li>
                <li><a href="#report">{t.home.footerProductLinks[2]}</a></li>
                <li><a href="#how">{t.home.footerProductLinks[3]}</a></li>
              </ul>
            </nav>
            <nav aria-label={t.home.footerFields}>
              <h4>{t.home.footerFields}</h4>
              <ul>
                {t.home.footerFieldsLinks.map((link) => (
                  <li key={link}><a href="#fields">{link}</a></li>
                ))}
              </ul>
            </nav>
            <nav aria-label={t.home.footerResources}>
              <h4>{t.home.footerResources}</h4>
              <ul>
                <li><a href="#faq">{t.home.footerResourcesLinks[0]}</a></li>
                <li><a href="#how">{t.home.footerResourcesLinks[1]}</a></li>
                <li><a href="#report">{t.home.footerResourcesLinks[2]}</a></li>
                <li><a href="#top">{t.home.footerResourcesLinks[3]}</a></li>
              </ul>
            </nav>
            <nav aria-label={t.home.footerCompany}>
              <h4>{t.home.footerCompany}</h4>
              <ul>
                {t.home.footerCompanyLinks.map((link) => (
                  <li key={link}><a href="#top">{link}</a></li>
                ))}
              </ul>
            </nav>
          </div>
          <div className="footer-bottom">
            <span>{t.home.footerCopyright}</span>
            <span>{t.home.footerSlogan}</span>
          </div>
        </div>
      </footer>
    </>
  );
}
