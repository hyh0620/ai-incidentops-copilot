"use client";

import { Loader2, Plus, RefreshCw } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { TaskBadge } from "@/components/Badge";
import { clientFetch } from "@/lib/api";
import { formatDate, taskStatusText } from "@/lib/format";
import type { RemediationTask, TaskStatus } from "@/types";

export default function AdminTasksPage() {
  const [tasks, setTasks] = useState<RemediationTask[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadTasks() {
    setLoading(true);
    const data = await clientFetch<RemediationTask[]>("/api/tasks");
    setTasks(data);
    setLoading(false);
  }

  useEffect(() => {
    loadTasks();
  }, []);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await clientFetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticket_id: Number(form.get("ticket_id")),
        title: form.get("title"),
        description: form.get("description"),
        assigned_to: form.get("assigned_to"),
        due_date: form.get("due_date") ? new Date(`${form.get("due_date")}T18:00:00`).toISOString() : null,
        status: "todo"
      })
    });
    event.currentTarget.reset();
    await loadTasks();
  }

  async function updateStatus(task: RemediationTask, status: TaskStatus) {
    await clientFetch(`/api/tasks/${task.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    });
    await loadTasks();
  }

  return (
    <AppShell mode="admin" title="处置任务" subtitle="查看、创建和更新工单处置任务">
      <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
        <form onSubmit={createTask} className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <div className="flex items-center gap-2">
            <Plus className="h-5 w-5 text-cyan-700" />
            <h2 className="text-lg font-semibold text-ink">创建任务</h2>
          </div>
          <div className="mt-4 space-y-3">
            <input name="ticket_id" type="number" min={1} required placeholder="关联工单 ID" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
            <input name="title" required placeholder="任务标题" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
            <textarea name="description" required rows={4} placeholder="任务描述" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
            <input name="assigned_to" required defaultValue="林峰" placeholder="负责人" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
            <input name="due_date" type="date" className="focus-ring w-full rounded-md border border-line px-3 py-2" />
            <button className="w-full rounded-md bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700">创建处置任务</button>
          </div>
        </form>

        <section className="rounded-lg border border-line bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-lg font-semibold text-ink">任务列表</h2>
            <button onClick={loadTasks} className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              <RefreshCw className="h-4 w-4" />
              刷新
            </button>
          </div>
          {loading ? (
            <div className="flex h-40 items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-cyan-700" />
            </div>
          ) : (
            <div className="divide-y divide-line">
              {tasks.map((task) => (
                <div key={task.id} className="grid gap-3 px-5 py-4 lg:grid-cols-[80px_1fr_120px_120px_180px] lg:items-center">
                  <span className="text-sm font-semibold text-cyan-700">#{task.ticket_id}</span>
                  <div>
                    <p className="font-medium text-ink">{task.title}</p>
                    <p className="mt-1 line-clamp-1 text-sm text-muted">{task.description}</p>
                  </div>
                  <span className="text-sm text-slate-700">{task.assigned_to}</span>
                  <TaskBadge value={task.status} />
                  <div className="flex gap-2">
                    {(["todo", "in_progress", "done"] as TaskStatus[]).map((status) => (
                      <button key={status} onClick={() => updateStatus(task, status)} className="rounded-md border border-line px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                        {taskStatusText[status]}
                      </button>
                    ))}
                  </div>
                  <p className="lg:col-start-2 text-xs text-muted">截止时间：{formatDate(task.due_date)}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
