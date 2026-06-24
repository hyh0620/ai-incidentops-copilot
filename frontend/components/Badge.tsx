import clsx from "clsx";
import type { Severity, TaskStatus, TicketStatus } from "@/types";
import { severityText, statusText, taskStatusText } from "@/lib/format";

export function SeverityBadge({ value }: { value: Severity }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold",
        value === "critical" && "bg-rose-100 text-rose-800",
        value === "high" && "bg-red-100 text-red-700",
        value === "medium" && "bg-amber-100 text-amber-700",
        value === "low" && "bg-emerald-100 text-emerald-700"
      )}
    >
      {severityText[value]}
    </span>
  );
}

export function StatusBadge({ value }: { value: TicketStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold",
        value === "open" && "bg-slate-100 text-slate-700",
        value === "triaged" && "bg-cyan-100 text-cyan-700",
        value === "in_progress" && "bg-indigo-100 text-indigo-700",
        value === "resolved" && "bg-emerald-100 text-emerald-700",
        value === "closed" && "bg-gray-200 text-gray-700"
      )}
    >
      {statusText[value]}
    </span>
  );
}

export function TaskBadge({ value }: { value: TaskStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold",
        value === "todo" && "bg-slate-100 text-slate-700",
        value === "in_progress" && "bg-violet-100 text-violet-700",
        value === "done" && "bg-emerald-100 text-emerald-700"
      )}
    >
      {taskStatusText[value]}
    </span>
  );
}
