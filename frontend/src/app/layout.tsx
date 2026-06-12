import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppAuthProvider } from "@/components/app-auth-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "PZ Deep Research",
  description: "面向 C 端用户的深度研究工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <AppAuthProvider>{children}</AppAuthProvider>
      </body>
    </html>
  );
}
