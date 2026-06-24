import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "智维工单 | AI IncidentOps Copilot",
  description: "智能运维工单平台，支持证据驱动分析与混合检索（RAG）"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
