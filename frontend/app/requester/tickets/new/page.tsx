"use client";

import { Loader2, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { publicApiBase } from "@/lib/api";

const categories = ["账号权限", "网络连接", "软件系统", "硬件设备", "安全风险", "数据库", "其他"];
const urgencies = ["低", "中", "高"];

export default function NewTicketPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const formData = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${publicApiBase}/api/tickets`, {
        method: "POST",
        body: formData
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = (await response.json()) as { ticket_id: number };
      router.push(`/requester/tickets/${result.ticket_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AppShell mode="requester" title="提交工单" subtitle="支持问题描述、截图和日志文件上传，提交后自动触发 AI 分析">
      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-lg border border-line bg-white p-5 shadow-soft">
          <div className="grid gap-5 md:grid-cols-2">
            <label className="md:col-span-2">
              <span className="text-sm font-medium text-slate-700">标题</span>
              <input name="title" required placeholder="例如：生产 API 返回 500 错误" className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2" />
            </label>
            <label className="md:col-span-2">
              <span className="text-sm font-medium text-slate-700">问题描述</span>
              <textarea
                name="description"
                required
                rows={7}
                placeholder="请描述发生时间、影响范围、错误提示、复现步骤等信息"
                className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2"
              />
            </label>
            <label>
              <span className="text-sm font-medium text-slate-700">可选类别</span>
              <select name="category" defaultValue="软件系统" className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2">
                {categories.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-sm font-medium text-slate-700">紧急程度</span>
              <select name="urgency" defaultValue="中" className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2">
                {urgencies.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-sm font-medium text-slate-700">受影响系统</span>
              <input name="affected_system" placeholder="例如：生产 API / 单点登录 / VPN" className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2" />
            </label>
            <label>
              <span className="text-sm font-medium text-slate-700">联系邮箱</span>
              <input name="contact_email" type="email" defaultValue="wangchen@example.com" className="focus-ring mt-2 w-full rounded-md border border-line px-3 py-2" />
            </label>
          </div>
          {error ? <div className="mt-5 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
          <div className="mt-6 flex items-center justify-end gap-3">
            <button type="button" onClick={() => router.push("/requester/dashboard")} className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              返回
            </button>
            <button disabled={submitting} className="inline-flex items-center gap-2 rounded-md bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-60">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              提交并分析
            </button>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="flex items-center gap-2">
              <UploadCloud className="h-5 w-5 text-cyan-700" />
              <h2 className="text-lg font-semibold text-ink">日志与截图证据</h2>
            </div>
            <label className="mt-4 block rounded-lg border border-dashed border-cyan-200 bg-cyan-50 p-4">
              <span className="text-sm font-medium text-cyan-900">截图上传</span>
              <input name="screenshot" type="file" accept="image/*" className="mt-3 block w-full text-sm text-cyan-900 file:mr-3 file:rounded-md file:border-0 file:bg-cyan-600 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" />
            </label>
            <label className="mt-4 block rounded-lg border border-dashed border-violet-200 bg-violet-50 p-4">
              <span className="text-sm font-medium text-violet-900">日志文件上传</span>
              <input name="log_file" type="file" accept=".log,.txt,.json,.csv" className="mt-3 block w-full text-sm text-violet-900 file:mr-3 file:rounded-md file:border-0 file:bg-violet-600 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white" />
            </label>
          </div>
          <div className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <h2 className="text-lg font-semibold text-ink">提交后返回内容</h2>
            <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
              <li>AI 预测类别与严重等级</li>
              <li>置信度与证据信号摘要</li>
              <li>混合检索命中的知识库来源</li>
              <li>推荐处置步骤与时间线</li>
            </ul>
          </div>
        </aside>
      </form>
    </AppShell>
  );
}
