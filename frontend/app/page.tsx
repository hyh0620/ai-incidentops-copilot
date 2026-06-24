import { ArrowRight, Bot, Boxes, BrainCircuit, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { serverFetch } from "@/lib/server-api";
import { percent, severityText } from "@/lib/format";
import type { AnalyticsSummary, Ticket } from "@/types";

export const dynamic = "force-dynamic";

const features = [
  { title: "问题提交与附件解析", text: "用户描述、运行日志和截图统一进入分析记录。", icon: FileText },
  { title: "混合检索（RAG）", text: "向量检索、BM25 关键词检索、RRF 融合和启发式排序查询知识库。", icon: Boxes },
  { title: "证据驱动智能分析", text: "分析结论和处理建议均附上对应文本、日志、OCR 或知识库证据。", icon: BrainCircuit },
  { title: "工单闭环与复核", text: "工单流转、处理任务、人工复核、分析记录和数据看板。", icon: ShieldCheck }
];

async function safeLoad() {
  try {
    const [summary, tickets] = await Promise.all([
      serverFetch<AnalyticsSummary>("/api/analytics/summary"),
      serverFetch<Ticket[]>("/api/tickets")
    ]);
    return { summary, tickets: tickets.slice(0, 3) };
  } catch {
    return { summary: null, tickets: [] as Ticket[] };
  }
}

export default async function LandingPage() {
  const { summary, tickets } = await safeLoad();
  return (
    <main className="min-h-screen bg-[#f5f7fb]">
      <section className="relative overflow-hidden border-b border-line bg-white">
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(6,182,212,0.12),rgba(79,70,229,0.08),rgba(16,185,129,0.08))]" />
        <div className="relative mx-auto grid min-h-[76vh] max-w-7xl items-center gap-10 px-6 py-16 lg:grid-cols-[1fr_440px]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-1 text-sm font-medium text-cyan-800">
              <Bot className="h-4 w-4" />
              AI IncidentOps Copilot
            </div>
            <h1 className="mt-8 text-5xl font-semibold tracking-normal text-ink sm:text-6xl">智维工单</h1>
            <p className="mt-5 text-2xl font-medium text-slate-700">智能运维工单平台</p>
            <p className="mt-6 max-w-3xl text-base leading-8 text-muted">
              面向 IT 运维与安全场景，支持问题提交、附件上传、工单流转、处理任务、人工复核、分析记录和数据看板；分析链路从用户描述、运行日志和截图中提取并脱敏关键信息，再通过混合检索查询知识库并生成带证据的结论。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/requester/dashboard" className="inline-flex items-center gap-2 rounded-md bg-cyan-600 px-5 py-3 text-sm font-semibold text-white shadow-soft hover:bg-cyan-700">
                用户报障端
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/admin/dashboard" className="inline-flex items-center gap-2 rounded-md border border-line bg-white px-5 py-3 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-50">
                管理后台
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="border-b border-line pb-4">
              <p className="text-sm font-semibold text-slate-500">本地演示数据状态</p>
              <p className="mt-2 text-3xl font-semibold text-ink">{summary ? summary.total_tickets : "-"}</p>
              <p className="mt-1 text-sm text-muted">{summary ? "演示工单来自本地 API" : "尚未导入演示数据或后端未启动"}</p>
            </div>
            <div className="mt-5 space-y-4">
              {tickets.length ? tickets.map((ticket) => (
                <div key={ticket.id} className="grid grid-cols-[1fr_80px_58px_58px] items-center gap-2 rounded-md border border-line bg-slate-50 px-3 py-3 text-sm">
                  <span className="truncate font-medium text-ink">{ticket.title}</span>
                  <span className="truncate text-muted">{ticket.predicted_category || "未分诊"}</span>
                  <span className="font-semibold text-red-600">{severityText[ticket.severity]}</span>
                  <span className="text-right font-semibold text-cyan-700">{percent(ticket.confidence)}</span>
                </div>
              )) : (
                <div className="rounded-md border border-dashed border-line bg-slate-50 px-3 py-6 text-sm text-muted">
                  运行 `python -m app.seed --reset` 后，这里会展示真实 API 返回的最近工单。
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-6 py-10">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <div key={feature.title} className="rounded-lg border border-line bg-white p-5 shadow-soft">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-violet-50 text-violet-700">
                  <Icon className="h-5 w-5" />
                </div>
                <h2 className="mt-4 text-lg font-semibold text-ink">{feature.title}</h2>
                <p className="mt-2 text-sm leading-6 text-muted">{feature.text}</p>
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}
