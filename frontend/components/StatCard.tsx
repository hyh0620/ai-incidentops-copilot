import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function StatCard({ label, value, hint, icon: Icon }: { label: string; value: ReactNode; hint?: string; icon: LucideIcon }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-5 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted">{label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-normal text-ink">{value}</p>
          {hint ? <p className="mt-2 text-xs text-muted">{hint}</p> : null}
        </div>
        <div className="rounded-md bg-cyan-50 p-2 text-cyan-700">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}
