import { Activity, BarChart3, BrainCircuit, Clock3, Database, FileText } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { BarList, TrendBars } from "@/components/SimpleChart";
import { StatCard } from "@/components/StatCard";
import { serverFetch } from "@/lib/server-api";
import type { AnalyticsSummary } from "@/types";

export const dynamic = "force-dynamic";

export default async function AnalyticsPage() {
  const [summary, categories, severity, trend, topIssues, kbHits, confidence, resolution] = await Promise.all([
    serverFetch<AnalyticsSummary>("/api/analytics/summary"),
    serverFetch<Array<{ name: string; value: number }>>("/api/analytics/categories"),
    serverFetch<Array<{ name: string; value: number }>>("/api/analytics/severity"),
    serverFetch<Array<{ date: string; count: number }>>("/api/analytics/trend"),
    serverFetch<Array<{ title: string; count: number }>>("/api/analytics/top-issues"),
    serverFetch<Array<{ title: string; hit_count: number }>>("/api/analytics/kb-hits"),
    serverFetch<Array<{ name: string; value: number }>>("/api/analytics/ai-confidence"),
    serverFetch<{ avg_hours: number; resolved_count: number; done_tasks: number }>("/api/analytics/resolution")
  ]);

  return (
    <AppShell mode="admin" title="数据分析" subtitle="工单趋势、重复问题、知识库命中和 AI 置信度分布">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="总工单数" value={summary.total_tickets} icon={FileText} hint="演示数据规模" />
        <StatCard label="平均解决时间" value={`${resolution.avg_hours}h`} icon={Clock3} hint={`${resolution.resolved_count} 个已解决工单`} />
        <StatCard label="已完成任务" value={resolution.done_tasks} icon={Activity} hint="已完成处置任务" />
        <StatCard label="AI 待复核" value={summary.ai_review_pending} icon={BrainCircuit} hint="待人工复核记录" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1fr]">
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-cyan-700" />
            <h2 className="text-lg font-semibold text-ink">最近 7 天工单趋势</h2>
          </div>
          <div className="mt-5">
            <TrendBars data={trend} />
          </div>
        </section>
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">AI 置信度分布</h2>
          <div className="mt-5">
            <BarList data={confidence} />
          </div>
        </section>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">按类别统计</h2>
          <div className="mt-5">
            <BarList data={categories} />
          </div>
        </section>
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">按严重等级统计</h2>
          <div className="mt-5">
            <BarList data={severity} />
          </div>
        </section>
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-violet-700" />
            <h2 className="text-lg font-semibold text-ink">知识库文章命中次数</h2>
          </div>
          <div className="mt-5">
            <BarList data={kbHits.map((item) => ({ name: item.title, value: item.hit_count }))} />
          </div>
        </section>
      </div>

      <section className="mt-6 rounded-lg border border-line bg-white p-5 shadow-soft">
        <h2 className="text-lg font-semibold text-ink">高频重复问题</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {topIssues.map((issue, index) => (
            <div key={issue.title} className="rounded-md border border-line p-4">
              <p className="text-sm font-semibold text-cyan-700">#{index + 1}</p>
              <p className="mt-2 font-medium text-ink">{issue.title}</p>
              <p className="mt-1 text-sm text-muted">出现 {issue.count} 次</p>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
