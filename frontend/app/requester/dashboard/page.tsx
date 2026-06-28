import { BookOpen, CheckCircle2, Clock3, FilePlus2, LifeBuoy } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { LocalDate } from "@/components/LocalDate";
import { StatCard } from "@/components/StatCard";
import { serverFetch } from "@/lib/server-api";
import type { KnowledgeBaseArticle, Ticket } from "@/types";

export const dynamic = "force-dynamic";

export default async function RequesterDashboardPage() {
  const [tickets, articles] = await Promise.all([
    serverFetch<Ticket[]>("/api/tickets"),
    serverFetch<KnowledgeBaseArticle[]>("/api/kb")
  ]);
  const recent = tickets.slice(0, 6);
  const inProgress = tickets.filter((ticket) => ticket.status === "in_progress" || ticket.status === "triaged").length;
  const resolved = tickets.filter((ticket) => ticket.status === "resolved" || ticket.status === "closed").length;
  const waiting = tickets.filter((ticket) => ticket.status === "open").length;

  return (
    <AppShell mode="requester" title="用户报障端" subtitle="提交问题、查看 AI 建议和工单处理时间线">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="我的工单总数" value={tickets.length} icon={LifeBuoy} hint="按当前演示身份统计" />
        <StatCard label="处理中工单数" value={inProgress} icon={Clock3} hint="已分诊和处理中" />
        <StatCard label="已解决工单数" value={resolved} icon={CheckCircle2} hint="已解决或已关闭" />
        <StatCard label="等待反馈工单数" value={waiting} icon={FilePlus2} hint="等待服务台分诊" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-line bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-lg font-semibold text-ink">最近提交的工单</h2>
            <Link href="/requester/tickets/new" className="rounded-md bg-cyan-600 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-700">
              新建工单
            </Link>
          </div>
          <div className="divide-y divide-line">
            {recent.map((ticket) => (
              <Link key={ticket.id} href={`/requester/tickets/${ticket.id}`} className="grid gap-3 px-5 py-4 hover:bg-slate-50 md:grid-cols-[1fr_110px_90px_88px] md:items-center">
                <div>
                  <p className="font-medium text-ink">{ticket.title}</p>
                  <p className="mt-1 line-clamp-1 text-sm text-muted">{ticket.description}</p>
                </div>
                <span className="text-sm text-muted">{ticket.predicted_category}</span>
                <SeverityBadge value={ticket.severity} />
                <StatusBadge value={ticket.status} />
              </Link>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-violet-700" />
            <h2 className="text-lg font-semibold text-ink">常见问题知识库</h2>
          </div>
          <div className="mt-4 space-y-3">
            {articles.slice(0, 6).map((article) => (
              <Link key={article.id} href="/requester/kb" className="block rounded-md border border-line p-3 hover:bg-slate-50">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-ink">{article.title}</p>
                  <span className="text-xs text-muted">{article.reading_time} 分钟</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-muted">{article.summary}</p>
              </Link>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted">最近同步：<LocalDate value={new Date().toISOString()} /></p>
        </section>
      </div>
    </AppShell>
  );
}
