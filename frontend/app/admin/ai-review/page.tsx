"use client";

import { Bot, Check, Loader2, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { clientFetch } from "@/lib/api";
import { aiReviewStatusText, formatDate, percent, reviewReasonDisplay, severityText, statusText } from "@/lib/format";
import type { AIReview, Severity } from "@/types";

const categories = ["账号权限", "网络连接", "软件系统", "系统资源", "安全风险", "数据库", "其他"];
const severities: Severity[] = ["low", "medium", "high", "critical"];

export default function AIReviewPage() {
  const [reviews, setReviews] = useState<AIReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<Record<number, { category: string; severity: Severity; note: string }>>({});

  async function loadReviews() {
    setLoading(true);
    const data = await clientFetch<AIReview[]>("/api/ai/reviews");
    setReviews(data);
    const nextDrafts: Record<number, { category: string; severity: Severity; note: string }> = {};
    data.forEach((review) => {
      nextDrafts[review.id] = {
        category: review.corrected_category || review.original_category,
        severity: review.corrected_severity || review.original_severity,
        note: review.reviewer_note || ""
      };
    });
    setDrafts(nextDrafts);
    setLoading(false);
  }

  useEffect(() => {
    loadReviews();
  }, []);

  async function updateReview(review: AIReview, mode: "approved" | "overridden") {
    const draft = drafts[review.id];
    await clientFetch(`/api/ai/reviews/${review.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: mode,
        corrected_category: mode === "overridden" ? draft.category : null,
        corrected_severity: mode === "overridden" ? draft.severity : null,
        correction_reason: mode === "overridden" ? draft.note || "人工复核覆盖，需要后续评估复盘" : null,
        reviewer_note: draft.note || (mode === "approved" ? "AI 建议已通过" : "人工覆盖 AI 判断")
      })
    });
    await loadReviews();
  }

  const pendingCount = reviews.filter((review) => review.status === "pending").length;

  return (
    <AppShell mode="admin" title="AI 复核中心" subtitle="低置信度、高危、安全风险、日志类工单进入人工复核">
      <div className="mb-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <p className="text-sm text-muted">待复核</p>
          <p className="mt-2 text-3xl font-semibold text-ink">{pendingCount}</p>
        </div>
        <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <p className="text-sm text-muted">已通过</p>
          <p className="mt-2 text-3xl font-semibold text-emerald-700">{reviews.filter((review) => review.status === "approved").length}</p>
        </div>
        <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <p className="text-sm text-muted">人工覆盖</p>
          <p className="mt-2 text-3xl font-semibold text-violet-700">{reviews.filter((review) => review.status === "overridden").length}</p>
        </div>
      </div>

      <section className="space-y-4">
        {loading ? (
          <div className="flex h-48 items-center justify-center rounded-lg border border-line bg-white">
            <Loader2 className="h-5 w-5 animate-spin text-cyan-700" />
          </div>
        ) : (
          reviews.map((review) => {
            const draft = drafts[review.id] || { category: review.original_category, severity: review.original_severity, note: "" };
            return (
              <div key={review.id} className="rounded-lg border border-line bg-white p-5 shadow-soft">
                <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
                  <div>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-semibold text-violet-700">
                          {review.status === "pending" ? <ShieldAlert className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                          AI 复核状态：{aiReviewStatusText(review.status)}
                        </div>
                        <Link href={`/admin/tickets/${review.ticket_id}`} className="mt-2 block text-xl font-semibold text-ink hover:text-cyan-700">
                          {review.ticket?.title}
                        </Link>
                        <p className="mt-2 text-sm leading-6 text-muted">{review.ticket?.description}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {(review.review_reasons || []).map((reason) => {
                            const display = reviewReasonDisplay(reason);
                            return (
                              <span key={reason} className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800" title={display.description}>
                                {display.title}
                              </span>
                            );
                          })}
                          {review.run_id ? (
                            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                              分析运行 {review.run_id.slice(0, 8)}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2 text-right">
                        {review.ticket ? (
                          <div>
                            <p className="mb-1 text-xs text-muted">工单状态：{statusText[review.ticket.status]}</p>
                            <StatusBadge value={review.ticket.status} />
                          </div>
                        ) : null}
                        <div>
                          <p className="mb-1 text-xs text-muted">AI 复核状态：{aiReviewStatusText(review.status)}</p>
                          <span className="rounded-md bg-violet-50 px-2 py-1 text-xs font-semibold text-violet-700">{aiReviewStatusText(review.status)}</span>
                        </div>
                        {review.ticket ? <SeverityBadge value={review.ticket.severity} /> : null}
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-4">
                      <div className="rounded-md bg-white p-3">
                        <p className="text-xs text-muted">工单状态</p>
                        <p className="mt-1 font-semibold text-ink">{review.ticket ? statusText[review.ticket.status] : "-"}</p>
                      </div>
                      <div className="rounded-md bg-white p-3">
                        <p className="text-xs text-muted">AI 复核状态</p>
                        <p className="mt-1 font-semibold text-ink">{aiReviewStatusText(review.status)}</p>
                      </div>
                      <div className="rounded-md bg-slate-50 p-3">
                        <p className="text-xs text-muted">原类别</p>
                        <p className="mt-1 font-semibold text-ink">{review.original_category}</p>
                      </div>
                      <div className="rounded-md bg-slate-50 p-3">
                        <p className="text-xs text-muted">原等级</p>
                        <p className="mt-1 font-semibold text-ink">{severityText[review.original_severity]}</p>
                      </div>
                      <div className="rounded-md bg-cyan-50 p-3">
                        <p className="text-xs text-cyan-700">AI 置信度</p>
                        <p className="mt-1 font-semibold text-cyan-950">{review.ticket ? percent(review.ticket.confidence) : "-"}</p>
                      </div>
                      <div className="rounded-md bg-violet-50 p-3">
                        <p className="text-xs text-violet-700">创建时间</p>
                        <p className="mt-1 font-semibold text-violet-950">{formatDate(review.created_at)}</p>
                      </div>
                    </div>
                    {(review.review_reasons || []).length ? (
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        {(review.review_reasons || []).map((reason) => {
                          const display = reviewReasonDisplay(reason);
                          return (
                            <div key={reason} className="rounded-md border border-amber-100 bg-amber-50 p-3">
                              <p className="text-sm font-semibold text-amber-900">{display.title}</p>
                              <p className="mt-1 text-xs leading-5 text-amber-800">{display.description}</p>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                  <div className="rounded-lg border border-line bg-slate-50 p-4">
                    <div className="grid gap-3">
                      <select
                        value={draft.category}
                        onChange={(event) => setDrafts((prev) => ({ ...prev, [review.id]: { ...draft, category: event.target.value } }))}
                        className="focus-ring rounded-md border border-line bg-white px-3 py-2"
                      >
                        {categories.map((item) => <option key={item}>{item}</option>)}
                      </select>
                      <select
                        value={draft.severity}
                        onChange={(event) => setDrafts((prev) => ({ ...prev, [review.id]: { ...draft, severity: event.target.value as Severity } }))}
                        className="focus-ring rounded-md border border-line bg-white px-3 py-2"
                      >
                        {severities.map((item) => <option key={item} value={item}>{severityText[item]}</option>)}
                      </select>
                      <textarea
                        value={draft.note}
                        onChange={(event) => setDrafts((prev) => ({ ...prev, [review.id]: { ...draft, note: event.target.value } }))}
                        placeholder="复核备注"
                        rows={3}
                        className="focus-ring rounded-md border border-line bg-white px-3 py-2"
                      />
                      <div className="flex gap-2">
                        <button onClick={() => updateReview(review, "approved")} className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
                          <Check className="h-4 w-4" />
                          通过建议
                        </button>
                        <button onClick={() => updateReview(review, "overridden")} className="flex-1 rounded-md bg-violet-600 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-700">
                          人工覆盖
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </section>
    </AppShell>
  );
}
