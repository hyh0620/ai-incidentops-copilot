import { AlertTriangle, Bot, Clock3, FileText, ShieldAlert, TimerReset } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { BarList } from "@/components/SimpleChart";
import { StatCard } from "@/components/StatCard";
import { formatDate, percent, severityText } from "@/lib/format";
import { serverFetch } from "@/lib/server-api";
import type { AIReview, AnalyticsSummary, Ticket } from "@/types";

export const dynamic = "force-dynamic";

export default async function AdminDashboardPage() {
  const [summary, categories, severity, tickets, reviews] = await Promise.all([
    serverFetch<AnalyticsSummary>("/api/analytics/summary"),
    serverFetch<Array<{ name: string; value: number }>>("/api/analytics/categories"),
    serverFetch<Array<{ name: string; value: number }>>("/api/analytics/severity"),
    serverFetch<Ticket[]>("/api/tickets"),
    serverFetch<AIReview[]>("/api/ai/reviews")
  ]);
  const highRisk = tickets.filter((ticket) => ticket.severity === "high" || ticket.severity === "critical").slice(0, 5);
  const pendingReviews = reviews.filter((review) => review.status === "pending").slice(0, 5);

  return (
    <AppShell mode="admin" title="管理后台总览" subtitle="总览工单量、风险事件、AI 复核和处置效率">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="总工单数" value={summary.total_tickets} icon={FileText} hint="历史累计演示工单" />
        <StatCard label="待处理工单数" value={summary.pending_tickets} icon={Clock3} hint="待分诊 / 已分诊 / 处理中" />
        <StatCard label="高危事件数" value={summary.high_risk_tickets} icon={ShieldAlert} hint="高 / 严重" />
        <StatCard label="平均解决时间" value={`${summary.avg_resolution_hours}h`} icon={TimerReset} hint="已解决工单均值" />
        <StatCard label="今日新增工单" value={summary.today_new_tickets} icon={AlertTriangle} hint="按本地数据库时间" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">工单类别分布</h2>
          <div className="mt-5">
            <BarList data={categories} />
          </div>
        </section>
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">严重等级分布</h2>
          <div className="mt-5">
            <BarList data={severity} />
          </div>
        </section>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-line bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-lg font-semibold text-ink">最近高风险事件</h2>
            <Link href="/admin/tickets" className="text-sm font-semibold text-cyan-700 hover:text-cyan-900">查看全部</Link>
          </div>
          <div className="divide-y divide-line">
            {highRisk.map((ticket) => (
              <Link key={ticket.id} href={`/admin/tickets/${ticket.id}`} className="grid gap-3 px-5 py-4 hover:bg-slate-50 md:grid-cols-[1fr_90px_92px_90px] md:items-center">
                <div>
                  <p className="font-medium text-ink">{ticket.title}</p>
                  <p className="mt-1 text-sm text-muted">{ticket.predicted_category} · {formatDate(ticket.created_at)}</p>
                </div>
                <SeverityBadge value={ticket.severity} />
                <StatusBadge value={ticket.status} />
                <span className="text-right text-sm font-semibold text-cyan-700">{percent(ticket.confidence)}</span>
              </Link>
            ))}
          </div>
        </section>
        <section className="rounded-lg border border-line bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-violet-700" />
              <h2 className="text-lg font-semibold text-ink">需要人工复核的 AI 判断</h2>
            </div>
            <Link href="/admin/ai-review" className="text-sm font-semibold text-cyan-700 hover:text-cyan-900">进入复核</Link>
          </div>
          <div className="divide-y divide-line">
            {pendingReviews.map((review) => (
              <Link key={review.id} href={`/admin/tickets/${review.ticket_id}`} className="block px-5 py-4 hover:bg-slate-50">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-ink">{review.ticket?.title}</p>
                    <p className="mt-1 text-sm text-muted">{review.original_category} · 原始等级 {severityText[review.original_severity]}</p>
                  </div>
                  <span className="rounded-md bg-violet-50 px-2 py-1 text-xs font-semibold text-violet-700">待复核</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
