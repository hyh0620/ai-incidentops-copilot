"use client";

import { Filter, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { clientFetch } from "@/lib/api";
import { formatDate, percent, severityText, statusText } from "@/lib/format";
import type { Severity, Ticket, TicketStatus } from "@/types";

const statuses: Array<"" | TicketStatus> = ["", "open", "triaged", "in_progress", "resolved", "closed"];
const severities: Array<"" | Severity> = ["", "low", "medium", "high", "critical"];
const categories = ["", "账号权限", "网络连接", "软件系统", "系统资源", "安全风险", "其他"];
const teams = ["", "一线服务台", "网络运维组", "平台工程组", "安全运营组", "身份与权限组"];

export default function AdminTicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [team, setTeam] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);
    if (category) params.set("predicted_category", category);
    if (team) params.set("assigned_team", team);
    if (search) params.set("search", search);
    return params.toString();
  }, [status, severity, category, team, search]);

  useEffect(() => {
    setLoading(true);
    clientFetch<Ticket[]>(`/api/tickets${query ? `?${query}` : ""}`)
      .then(setTickets)
      .finally(() => setLoading(false));
  }, [query]);

  return (
    <AppShell mode="admin" title="工单中心" subtitle="筛选类别、状态、严重等级和分配团队">
      <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
        <div className="grid gap-3 lg:grid-cols-[1fr_150px_150px_150px_160px]">
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索标题和描述" className="focus-ring w-full rounded-md border border-line py-2 pl-9 pr-3" />
          </label>
          <select value={status} onChange={(event) => setStatus(event.target.value)} className="focus-ring rounded-md border border-line px-3 py-2">
            {statuses.map((item) => <option key={item || "all"} value={item}>{item ? statusText[item] : "全部状态"}</option>)}
          </select>
          <select value={severity} onChange={(event) => setSeverity(event.target.value)} className="focus-ring rounded-md border border-line px-3 py-2">
            {severities.map((item) => <option key={item || "all"} value={item}>{item ? severityText[item] : "全部等级"}</option>)}
          </select>
          <select value={category} onChange={(event) => setCategory(event.target.value)} className="focus-ring rounded-md border border-line px-3 py-2">
            {categories.map((item) => <option key={item || "all"} value={item}>{item || "全部类别"}</option>)}
          </select>
          <select value={team} onChange={(event) => setTeam(event.target.value)} className="focus-ring rounded-md border border-line px-3 py-2">
            {teams.map((item) => <option key={item || "all"} value={item}>{item || "全部团队"}</option>)}
          </select>
        </div>
        <div className="mt-4 flex items-center gap-2 text-sm text-muted">
          <Filter className="h-4 w-4" />
          当前结果：{loading ? "加载中" : `${tickets.length} 条工单`}
        </div>
      </section>

      <section className="mt-6 overflow-hidden rounded-lg border border-line bg-white shadow-soft">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-line text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-muted">
              <tr>
                <th className="px-5 py-3">工单标题</th>
                <th className="px-5 py-3">提交人</th>
                <th className="px-5 py-3">AI 预测类别</th>
                <th className="px-5 py-3">严重等级</th>
                <th className="px-5 py-3">状态</th>
                <th className="px-5 py-3">创建时间</th>
                <th className="px-5 py-3">分配团队</th>
                <th className="px-5 py-3">置信度</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {tickets.map((ticket) => (
                <tr key={ticket.id} className="hover:bg-slate-50">
                  <td className="px-5 py-4">
                    <Link href={`/admin/tickets/${ticket.id}`} className="font-medium text-ink hover:text-cyan-700">{ticket.title}</Link>
                    <p className="mt-1 line-clamp-1 text-xs text-muted">{ticket.description}</p>
                  </td>
                  <td className="px-5 py-4 text-slate-700">{ticket.requester?.name || "-"}</td>
                  <td className="px-5 py-4 text-slate-700">{ticket.predicted_category}</td>
                  <td className="px-5 py-4"><SeverityBadge value={ticket.severity} /></td>
                  <td className="px-5 py-4"><StatusBadge value={ticket.status} /></td>
                  <td className="px-5 py-4 text-muted">{formatDate(ticket.created_at)}</td>
                  <td className="px-5 py-4 text-slate-700">{ticket.assigned_team || "未分配"}</td>
                  <td className="px-5 py-4 font-semibold text-cyan-700">{percent(ticket.confidence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
