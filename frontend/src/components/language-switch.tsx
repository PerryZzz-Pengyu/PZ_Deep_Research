"use client";

import { useI18n } from "@/lib/i18n";

export function LanguageSwitch() {
  const { locale, setLocale } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label="Language">
      <button type="button" aria-pressed={locale === "zh"} onClick={() => setLocale("zh")}>
        中文
      </button>
      <button type="button" aria-pressed={locale === "en"} onClick={() => setLocale("en")}>
        EN
      </button>
    </div>
  );
}
