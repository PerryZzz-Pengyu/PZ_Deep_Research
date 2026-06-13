import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { AppAuthProvider } from "@/components/app-auth-provider";
import { I18nProvider } from "@/lib/i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: "PZ Deep Research — 带出处的 AI 深度研究助手",
  description:
    "PZ Deep Research 检索实时网络、阅读来源、抽取证据，并撰写带编号引用的结构化研究报告。证据优先，永远有出处。",
};

export const viewport: Viewport = {
  themeColor: "#070a12",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html className="dark" lang="zh-CN" suppressHydrationWarning>
      <body>
        <I18nProvider>
          <AppAuthProvider>{children}</AppAuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
