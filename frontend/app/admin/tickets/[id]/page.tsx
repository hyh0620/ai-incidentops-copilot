"use client";

import { Bot, CheckCircle2, Database, FileArchive, GitCompare, Loader2, MessageSquare, Paperclip, RefreshCw, Save, ShieldCheck, Workflow } from "lucide-react";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SeverityBadge, StatusBadge, TaskBadge } from "@/components/Badge";
import { clientFetch } from "@/lib/api";
import {
  attachmentTypeText,
  eventTypeText,
  evidenceAvailabilityText,
  evidenceSourceTypeText,
  formatDate,
  percent,
  providerText,
  severityText,
  stageNameText,
  stageStatusText,
  statusText,
  timelineContentText
} from "@/lib/format";
import type { Severity, TicketDetail, TicketStatus } from "@/types";

const statusOptions: TicketStatus[] = ["open", "triaged", "in_progress", "resolved", "closed"];
const severityOptions: Severity[] = ["low", "medium", "high", "critical"];
const teams = ["一线服务台", "网络运维组", "平台工程组", "安全运营组", "身份与权限组"];

function scoreText(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return value.toFixed(4);
}

function sourceScore(source: { rerank_score?: number | null; final_score?: number; fusion_score?: number }) {
  return source.rerank_score ?? source.final_score ?? source.fusion_score ?? 0;
}

export default function AdminTicketDetailPage() {
  const params = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<TicketStatus>("triaged");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [assignedTeam, setAssignedTeam] = useState("");
  const [internalNote, setInternalNote] = useState("");
  const [userReply, setUserReply] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskOwner, setTaskOwner] = useState("林峰");
  const [taskDueDate, setTaskDueDate] = useState("");
  const [reanalyzing, setReanalyzing] = useState(false);

  const loadTicket = useCallback(async () => {
    setLoading(true);
    const data = await clientFetch<TicketDetail>(`/api/tickets/${params.id}`);
    setTicket(data);
    setStatus(data.status);
    setSeverity(data.severity);
    setAssignedTeam(data.assigned_team || "");
    setLoading(false);
  }, [params.id]);

  useEffect(() => {
    loadTicket();
  }, [loadTicket]);

  async function saveTicket(nextStatus?: TicketStatus) {
    setSaving(true);
    const data = await clientFetch<TicketDetail>(`/api/tickets/${params.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: nextStatus || status,
        severity,
        assigned_team: assignedTeam || null,
        internal_note: internalNote || undefined,
        user_reply: userReply || undefined
      })
    });
    setTicket(data);
    setStatus(data.status);
    setSeverity(data.severity);
    setAssignedTeam(data.assigned_team || "");
    setInternalNote("");
    setUserReply("");
    setSaving(false);
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ticket) return;
    await clientFetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticket_id: ticket.id,
        title: taskTitle,
        description: taskDescription,
        assigned_to: taskOwner,
        due_date: taskDueDate ? new Date(`${taskDueDate}T18:00:00`).toISOString() : null,
        status: "todo"
      })
    });
    setTaskTitle("");
    setTaskDescription("");
    setTaskDueDate("");
    await loadTicket();
  }

  async function reanalyze() {
    setReanalyzing(true);
    await clientFetch(`/api/tickets/${params.id}/reanalyze`, { method: "POST" });
    await loadTicket();
    setReanalyzing(false);
  }

  const latestAudit = ticket?.ai_analysis_audits?.[0];
  const evidenceItems = latestAudit?.evidence || [];
  const retrievedSources = latestAudit?.retrieved_sources?.length ? latestAudit.retrieved_sources : ticket?.related_kb_articles || [];
  const finalDecision = latestAudit?.final_decision || {};
  const fallbackReason = typeof finalDecision.fallback_reason === "string" ? finalDecision.fallback_reason : null;
  const llmValidationStatus = typeof finalDecision.llm_validation_status === "string" ? finalDecision.llm_validation_status : null;
  const signalTags = Array.from(new Set(evidenceItems.flatMap((item) => item.signal_tags || []))).slice(0, 12);
  const analysisSourceText = fallbackReason
    ? `已回退至规则分诊：${fallbackReason}`
    : latestAudit?.provider === "openai_compatible" && llmValidationStatus === "passed"
      ? "分析来源：LLM 结构化分析（证据校验通过）"
      : "分析来源：规则分诊";

  return (
    <AppShell mode="admin" title="工单详情" subtitle="复核 AI 判断、分配团队、创建处置任务并记录处理过程">
      {loading || !ticket ? (
        <div className="flex h-64 items-center justify-center rounded-lg border border-line bg-white">
          <Loader2 className="h-6 w-6 animate-spin text-cyan-700" />
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_390px]">
          <section className="space-y-6">
            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-cyan-700">#{ticket.id} · {ticket.affected_system}</p>
                  <h2 className="mt-2 text-2xl font-semibold text-ink">{ticket.title}</h2>
                  <p className="mt-2 text-sm text-muted">提交人：{ticket.requester?.name} · {ticket.requester?.department} · {formatDate(ticket.created_at)}</p>
                </div>
                <div className="flex gap-2">
                  <SeverityBadge value={ticket.severity} />
                  <StatusBadge value={ticket.status} />
                </div>
              </div>
              <p className="mt-5 whitespace-pre-wrap rounded-md bg-slate-50 p-4 text-sm leading-7 text-slate-700">{ticket.description}</p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-violet-700" />
                  <h2 className="text-lg font-semibold text-ink">AI 分析结果</h2>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-md bg-cyan-50 p-3">
                    <p className="text-xs text-cyan-700">预测类别</p>
                    <p className="mt-1 font-semibold text-cyan-950">{ticket.predicted_category}</p>
                  </div>
                  <div className="rounded-md bg-red-50 p-3">
                    <p className="text-xs text-red-700">严重等级</p>
                    <p className="mt-1 font-semibold text-red-950">{severityText[ticket.severity]}</p>
                  </div>
                  <div className="rounded-md bg-emerald-50 p-3">
                    <p className="text-xs text-emerald-700">置信度</p>
                    <p className="mt-1 font-semibold text-emerald-950">{percent(ticket.confidence)}</p>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md border border-line bg-slate-50 p-3">
                    <p className="text-xs text-muted">分诊提供方</p>
                    <p className="mt-1 break-words text-sm font-semibold text-ink">{providerText(latestAudit?.provider || "rule_fallback")}</p>
                  </div>
                  <div className="rounded-md border border-line bg-slate-50 p-3">
                    <p className="text-xs text-muted">检索方式</p>
                    <p className="mt-1 break-words text-sm font-semibold text-ink">{providerText(latestAudit?.retrieval_mode || "local hybrid retrieval")}</p>
                  </div>
                </div>
                <div className={`mt-3 rounded-md border p-3 text-sm leading-6 ${fallbackReason ? "border-amber-200 bg-amber-50 text-amber-800" : "border-cyan-100 bg-cyan-50 text-cyan-900"}`}>
                  {analysisSourceText}
                  {llmValidationStatus ? <span className="ml-2 text-xs font-semibold">校验状态：{llmValidationStatus}</span> : null}
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md border border-line bg-white p-3">
                    <p className="text-xs text-muted">分析运行 / 追踪 ID</p>
                    <p className="mt-1 break-all text-xs font-semibold text-ink">{latestAudit?.run_id || "-"} / {latestAudit?.trace_id || "-"}</p>
                  </div>
                  <div className="rounded-md border border-line bg-white p-3">
                    <p className="text-xs text-muted">索引版本</p>
                    <p className="mt-1 break-words text-xs font-semibold text-ink">{latestAudit?.index_version || "hybrid-faiss-bm25-rrf-v2"}</p>
                  </div>
                </div>
                {latestAudit?.uncertainty ? (
                  <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
                    不确定性：{latestAudit.uncertainty}
                  </div>
                ) : null}
                <div className="mt-4 rounded-md border border-line bg-white p-3">
                  <p className="text-xs font-semibold text-muted">命中信号</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {signalTags.length ? signalTags.map((tag) => (
                      <span key={tag} className="rounded-md bg-cyan-50 px-2 py-1 text-xs font-semibold text-cyan-700">{tag}</span>
                    )) : <span className="text-xs text-muted">暂无结构化信号，查看下方证据区确认日志 / OCR 提取结果。</span>}
                  </div>
                </div>
                <details className="mt-4 rounded-md border border-line bg-slate-50">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700">原始分析记录（调试）</summary>
                  <pre className="max-h-64 overflow-auto border-t border-line bg-slate-950 p-4 text-xs leading-5 text-cyan-50">
                    {JSON.stringify(ticket.ai_signals, null, 2)}
                  </pre>
                </details>
              </div>

              <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-cyan-700" />
                  <h2 className="text-lg font-semibold text-ink">混合检索处置建议</h2>
                </div>
                <p className="mt-4 text-sm leading-7 text-slate-700">{ticket.suggested_resolution}</p>
                <div className="mt-4 space-y-2">
                  {ticket.related_kb_articles.map((article) => (
                    <div key={`${article.article_id}-${article.chunk_id}`} className="rounded-md border border-line p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-ink">{article.title}</p>
                        <span className="text-xs font-semibold text-cyan-700">{scoreText(sourceScore(article))}</span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-sm text-muted">{article.summary}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-cyan-700" />
                <h2 className="text-lg font-semibold text-ink">AI 证据与知识库来源</h2>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                <div>
                  <h3 className="text-sm font-semibold text-slate-700">文本证据 / 日志证据 / OCR 证据</h3>
                  <div className="mt-3 space-y-3">
                    {evidenceItems.length ? (
                      evidenceItems.map((item, index) => (
                        <div key={`${item.source_type}-${index}`} className="rounded-md border border-line bg-slate-50 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-ink">{evidenceSourceTypeText(item.source_type)} · {item.source_name}</p>
                            <span className="rounded-md bg-white px-2 py-1 text-xs text-muted">{evidenceAvailabilityText(item)}</span>
                          </div>
                          <p className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-700">{item.excerpt || item.error || "未提取到可用证据"}</p>
                          {item.redacted ? <p className="mt-2 text-xs font-semibold text-amber-700">已脱敏展示</p> : null}
                          {(item.signal_tags?.length || item.signals?.length) ? (
                            <p className="mt-2 text-xs text-cyan-700">命中信号：{(item.signal_tags || item.signals || []).join(", ")}</p>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-muted">暂无可追溯证据，建议重新上传日志或截图后执行重新分析。</p>
                    )}
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-700">知识库片段来源</h3>
                  <div className="mt-3 space-y-3">
                    {retrievedSources.length ? (
                      retrievedSources.map((source) => (
                        <div key={`${source.article_id}-${source.chunk_id}`} className="rounded-md border border-line p-3">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="font-medium text-ink">{source.title}</p>
                              <p className="mt-1 text-xs text-muted">
                                文章 #{source.article_id} · 片段 #{source.chunk_id} · {source.category}
                                {source.historical_snapshot ? " · 历史快照" : ""}
                              </p>
                            </div>
                            <span className="rounded-md bg-cyan-50 px-2 py-1 text-xs font-semibold text-cyan-700">{scoreText(sourceScore(source))}</span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-slate-700">{source.evidence_excerpt || source.evidence_excerpt_snapshot || source.chunk_summary}</p>
                          <div className="mt-3 grid grid-cols-4 gap-2 text-xs text-muted">
                            <span>向量 {scoreText(source.dense_score)}</span>
                            <span>BM25 {scoreText(source.lexical_score)}</span>
                            <span>融合 {scoreText(source.fusion_score)}</span>
                            <span>重排 {scoreText(source.rerank_score)}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-muted">未找到足够知识库来源。</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <GitCompare className="h-5 w-5 text-violet-700" />
                  <h2 className="text-lg font-semibold text-ink">AI 分析运行记录</h2>
                </div>
                <button
                  onClick={reanalyze}
                  disabled={reanalyzing}
                  className="inline-flex items-center gap-2 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-semibold text-cyan-800 hover:bg-cyan-100 disabled:opacity-60"
                >
                  {reanalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  重新分析
                </button>
              </div>
              <div className="mt-4 grid gap-4 xl:grid-cols-[0.75fr_1.25fr]">
                <div className="space-y-3">
                  {ticket.ai_analysis_audits?.map((run) => (
                    <div key={run.run_id} className="rounded-md border border-line bg-slate-50 p-3">
                      <p className="break-all text-xs font-semibold text-ink">{run.run_id}</p>
                      <p className="mt-1 text-xs text-muted">{formatDate(run.created_at)} · {run.provider}</p>
                      <p className="mt-1 text-xs text-muted">引用片段：{run.source_chunk_ids?.join(", ") || "-"}</p>
                      {typeof run.final_decision?.fallback_reason === "string" ? (
                        <p className="mt-1 text-xs font-semibold text-amber-700">回退原因：{run.final_decision.fallback_reason}</p>
                      ) : null}
                    </div>
                  ))}
                  {!ticket.ai_analysis_audits?.length ? <p className="text-sm text-muted">暂无分析运行记录。</p> : null}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-700">当前分析流水线追踪</h3>
                  <div className="mt-3 space-y-2">
                    {(latestAudit?.stage_traces || []).map((stage) => (
                      <div key={`${stage.name}-${stage.started_at}`} className="grid gap-2 rounded-md border border-line p-3 text-sm md:grid-cols-[1fr_110px_90px]">
                        <div>
                          <p className="font-semibold text-ink">{stageNameText(stage.name)}</p>
                          <p className="mt-1 text-xs text-muted">提供方：{stage.provider ? providerText(stage.provider) : "内部流程"} {stage.error ? `· ${stage.error}` : ""}</p>
                        </div>
                        <span className="text-xs font-medium text-slate-700">{stageStatusText(stage.status)}</span>
                        <span className="text-xs font-semibold text-cyan-700">{stage.duration_ms} 毫秒</span>
                      </div>
                    ))}
                    {!latestAudit?.stage_traces?.length ? <p className="text-sm text-muted">暂无追踪记录。</p> : null}
                  </div>
                  {latestAudit?.previous_diff ? (
                    <pre className="mt-4 max-h-40 overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-cyan-50">
                      {JSON.stringify(latestAudit.previous_diff, null, 2)}
                    </pre>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex items-center gap-2">
                <Workflow className="h-5 w-5 text-cyan-700" />
                <h2 className="text-lg font-semibold text-ink">工单时间线</h2>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {ticket.timeline.map((event) => (
                  <div key={event.id} className="rounded-md border border-line p-3">
                    <p className="text-sm font-medium text-ink">{timelineContentText(event.content)}</p>
                    <p className="mt-1 text-xs text-muted">{formatDate(event.created_at)} · {eventTypeText(event.event_type)}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <aside className="space-y-6">
            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex items-center gap-2">
                <Save className="h-5 w-5 text-cyan-700" />
                <h2 className="text-lg font-semibold text-ink">管理员操作</h2>
              </div>
              <div className="mt-4 grid gap-3">
                <label>
                  <span className="text-sm font-medium text-slate-700">状态</span>
                  <select value={status} onChange={(event) => setStatus(event.target.value as TicketStatus)} className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2">
                    {statusOptions.map((item) => <option key={item} value={item}>{statusText[item]}</option>)}
                  </select>
                </label>
                <label>
                  <span className="text-sm font-medium text-slate-700">严重等级</span>
                  <select value={severity} onChange={(event) => setSeverity(event.target.value as Severity)} className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2">
                    {severityOptions.map((item) => <option key={item} value={item}>{severityText[item]}</option>)}
                  </select>
                </label>
                <label>
                  <span className="text-sm font-medium text-slate-700">分配团队</span>
                  <select value={assignedTeam} onChange={(event) => setAssignedTeam(event.target.value)} className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2">
                    <option value="">未分配</option>
                    {teams.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>
                  <span className="text-sm font-medium text-slate-700">内部备注</span>
                  <textarea value={internalNote} onChange={(event) => setInternalNote(event.target.value)} rows={3} className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2" />
                </label>
                <label>
                  <span className="text-sm font-medium text-slate-700">回复给用户</span>
                  <textarea value={userReply} onChange={(event) => setUserReply(event.target.value)} rows={3} className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2" />
                </label>
                <div className="flex gap-2">
                  <button onClick={() => saveTicket()} disabled={saving} className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-60">
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    保存
                  </button>
                  <button onClick={() => saveTicket("resolved")} className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-100">
                    <CheckCircle2 className="h-4 w-4" />
                    解决
                  </button>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex items-center gap-2">
                <Paperclip className="h-5 w-5 text-violet-700" />
                <h2 className="text-lg font-semibold text-ink">截图与日志</h2>
              </div>
              <div className="mt-4 space-y-2">
                {ticket.attachments.map((item) => (
                  <div key={item.id} className="flex items-center gap-3 rounded-md border border-line p-3">
                    <FileArchive className="h-4 w-4 text-muted" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">{item.file_name}</p>
                      <p className="text-xs text-muted">{attachmentTypeText(item.file_type)} · {item.mime_type || "未知 MIME"}</p>
                      <a className="text-xs font-semibold text-cyan-700" href={`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/tickets/${ticket.id}/attachments/${item.id}/download`}>
                        受控下载
                      </a>
                    </div>
                  </div>
                ))}
                {!ticket.attachments.length ? <p className="text-sm text-muted">未上传附件</p> : null}
              </div>
            </div>

            <form onSubmit={createTask} className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-cyan-700" />
                <h2 className="text-lg font-semibold text-ink">创建处置任务</h2>
              </div>
              <div className="mt-4 space-y-3">
                <input required value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="任务标题" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
                <textarea required value={taskDescription} onChange={(event) => setTaskDescription(event.target.value)} placeholder="任务描述" rows={3} className="focus-ring w-full rounded-md border border-line px-3 py-2" />
                <input value={taskOwner} onChange={(event) => setTaskOwner(event.target.value)} placeholder="负责人" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
                <input type="date" value={taskDueDate} onChange={(event) => setTaskDueDate(event.target.value)} className="focus-ring w-full rounded-md border border-line px-3 py-2" />
                <button className="w-full rounded-md bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700">创建任务</button>
              </div>
            </form>

            <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
              <h2 className="text-lg font-semibold text-ink">处置任务</h2>
              <div className="mt-4 space-y-2">
                {ticket.tasks.map((task) => (
                  <div key={task.id} className="rounded-md border border-line p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-ink">{task.title}</p>
                      <TaskBadge value={task.status} />
                    </div>
                    <p className="mt-1 text-sm text-muted">{task.assigned_to} · {formatDate(task.due_date)}</p>
                  </div>
                ))}
                {!ticket.tasks.length ? <p className="text-sm text-muted">暂无任务</p> : null}
              </div>
            </div>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
