import { FileText, Paperclip, Sparkles } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { SeverityBadge, StatusBadge, TaskBadge } from "@/components/Badge";
import { LocalDate } from "@/components/LocalDate";
import { attachmentTypeText, eventTypeText, percent, severityText, timelineContentText } from "@/lib/format";
import { serverFetch } from "@/lib/server-api";
import type { TicketDetail } from "@/types";

export const dynamic = "force-dynamic";

export default async function RequesterTicketDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let ticket: TicketDetail | null = null;
  try {
    ticket = await serverFetch<TicketDetail>(`/api/tickets/${id}`);
  } catch {
    return (
      <AppShell mode="requester" title="工单详情" subtitle="查看 AI 分析结果、管理员回复和处理时间线">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-amber-900">
          <h2 className="text-lg font-semibold">无法查看该工单</h2>
          <p className="mt-2 text-sm leading-6">
            当前演示身份没有权限访问该工单，或工单不存在。请切换到对应的报障员工身份，或使用管理员入口查看全部工单。
          </p>
          <Link href="/requester/dashboard" className="mt-4 inline-flex rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700">
            返回用户概览
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell mode="requester" title="工单详情" subtitle="查看 AI 分析结果、管理员回复和处理时间线">
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="space-y-6">
          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-ink">{ticket.title}</h2>
                <p className="mt-2 text-sm text-muted">提交人：{ticket.requester?.name} · <LocalDate value={ticket.created_at} /></p>
              </div>
              <div className="flex gap-2">
                <SeverityBadge value={ticket.severity} />
                <StatusBadge value={ticket.status} />
              </div>
            </div>
            <p className="mt-5 whitespace-pre-wrap rounded-md bg-slate-50 p-4 text-sm leading-7 text-slate-700">{ticket.description}</p>
          </div>

          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-cyan-700" />
              <h2 className="text-lg font-semibold text-ink">AI 建议</h2>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-md bg-cyan-50 p-3">
                <p className="text-xs text-cyan-700">预测类别</p>
                <p className="mt-1 font-semibold text-cyan-950">{ticket.predicted_category}</p>
              </div>
              <div className="rounded-md bg-violet-50 p-3">
                <p className="text-xs text-violet-700">严重等级</p>
                <p className="mt-1 font-semibold text-violet-950">{severityText[ticket.severity]}</p>
              </div>
              <div className="rounded-md bg-emerald-50 p-3">
                <p className="text-xs text-emerald-700">置信度</p>
                <p className="mt-1 font-semibold text-emerald-950">{percent(ticket.confidence)}</p>
              </div>
            </div>
            <p className="mt-4 text-sm leading-7 text-slate-700">{ticket.suggested_resolution}</p>
            <ol className="mt-4 space-y-2">
              {ticket.next_steps.map((step, index) => (
                <li key={step} className="flex gap-3 rounded-md border border-line px-3 py-2 text-sm text-slate-700">
                  <span className="font-semibold text-cyan-700">{index + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <h2 className="text-lg font-semibold text-ink">管理员回复</h2>
            <div className="mt-4 space-y-3">
              {ticket.timeline.filter((event) => event.event_type === "admin_reply").length ? (
                ticket.timeline
                  .filter((event) => event.event_type === "admin_reply")
                  .map((event) => (
                    <div key={event.id} className="rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700">
                      {timelineContentText(event.content)}
                    </div>
                  ))
              ) : (
                <p className="text-sm text-muted">暂无管理员回复</p>
              )}
            </div>
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="flex items-center gap-2">
              <Paperclip className="h-5 w-5 text-violet-700" />
              <h2 className="text-lg font-semibold text-ink">上传附件</h2>
            </div>
            <div className="mt-4 space-y-2">
              {ticket.attachments.length ? (
                ticket.attachments.map((item) => (
                  <div key={item.id} className="rounded-md border border-line px-3 py-2 text-sm">
                    <p className="font-medium text-ink">{item.file_name}</p>
                    <p className="text-xs text-muted">{attachmentTypeText(item.file_type)}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted">未上传附件</p>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <h2 className="text-lg font-semibold text-ink">相关知识库文章</h2>
            <div className="mt-4 space-y-3">
              {ticket.related_kb_articles.map((article) => (
                <Link key={article.id} href="/requester/kb" className="block rounded-md border border-line p-3 hover:bg-slate-50">
                  <p className="font-medium text-ink">{article.title}</p>
                  <p className="mt-1 line-clamp-2 text-sm text-muted">{article.summary}</p>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-cyan-700" />
              <h2 className="text-lg font-semibold text-ink">工单时间线</h2>
            </div>
            <div className="mt-4 space-y-4">
              {ticket.timeline.map((event) => (
                <div key={event.id} className="border-l-2 border-cyan-200 pl-3">
                  <p className="text-sm font-medium text-ink">{timelineContentText(event.content)}</p>
                  <p className="mt-1 text-xs text-muted"><LocalDate value={event.created_at} /> · {eventTypeText(event.event_type)}</p>
                </div>
              ))}
            </div>
          </div>

          {ticket.tasks.length ? (
            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <h2 className="text-lg font-semibold text-ink">处置任务</h2>
              <div className="mt-4 space-y-2">
                {ticket.tasks.map((task) => (
                  <div key={task.id} className="rounded-md border border-line p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-ink">{task.title}</p>
                      <TaskBadge value={task.status} />
                    </div>
                    <p className="mt-1 text-sm text-muted">{task.assigned_to}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </AppShell>
  );
}
