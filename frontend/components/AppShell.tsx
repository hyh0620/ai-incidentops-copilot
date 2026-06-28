"use client";

import clsx from "clsx";
import {
  Activity,
  BarChart3,
  BookOpen,
  ClipboardList,
  FilePlus2,
  Home,
  LayoutDashboard,
  ShieldCheck,
  Sparkles,
  UsersRound
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { DemoPersonaSwitcher } from "@/components/DemoPersonaSwitcher";

const requesterNav = [
  { href: "/requester/dashboard", label: "用户概览", icon: LayoutDashboard },
  { href: "/requester/tickets/new", label: "提交工单", icon: FilePlus2 },
  { href: "/requester/kb", label: "知识库", icon: BookOpen }
];

const adminNav = [
  { href: "/admin/dashboard", label: "管理概览", icon: LayoutDashboard },
  { href: "/admin/tickets", label: "工单中心", icon: ClipboardList },
  { href: "/admin/tasks", label: "处置任务", icon: Activity },
  { href: "/admin/ai-review", label: "AI 复核", icon: ShieldCheck },
  { href: "/admin/analytics", label: "数据分析", icon: BarChart3 }
];

export function AppShell({
  mode,
  title,
  subtitle,
  children
}: {
  mode: "requester" | "admin";
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const nav = mode === "admin" ? adminNav : requesterNav;
  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-line bg-white lg:block">
        <div className="flex h-16 items-center gap-3 border-b border-line px-5">
          <div className="rounded-md bg-gradient-to-br from-cyan-500 to-violet-600 p-2 text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold text-ink">智维工单</p>
            <p className="text-xs text-muted">智能运维工单平台</p>
          </div>
        </div>
        <nav className="space-y-1 px-3 py-4">
          <Link
            href="/"
            className="mb-3 flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted hover:bg-slate-50 hover:text-ink"
          >
            <Home className="h-4 w-4" />
            项目首页
          </Link>
          {nav.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition",
                  active ? "bg-cyan-50 text-cyan-800" : "text-slate-600 hover:bg-slate-50 hover:text-ink"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="absolute bottom-4 left-3 right-3 rounded-lg border border-cyan-100 bg-cyan-50 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-cyan-900">
            <UsersRound className="h-4 w-4" />
            本地演示环境
          </div>
          <p className="mt-1 text-xs leading-5 text-cyan-800">当前使用本地演示身份与合成数据；分析来源、降级状态和人工复核原因会在工单详情中标记。</p>
        </div>
      </aside>
      <main className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-line bg-white/90 px-5 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-[0.18em] text-cyan-700">{mode === "admin" ? "管理后台" : "用户报障端"}</p>
              <h1 className="mt-1 text-2xl font-semibold tracking-normal text-ink">{title}</h1>
              {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
            </div>
            <div className="flex items-center gap-3">
              <DemoPersonaSwitcher />
              <Link
                href={mode === "admin" ? "/requester/dashboard" : "/admin/dashboard"}
                className="hidden rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 sm:inline-flex"
              >
                切换入口
              </Link>
            </div>
          </div>
        </header>
        <div className="mx-auto max-w-7xl px-5 py-6">{children}</div>
      </main>
    </div>
  );
}
