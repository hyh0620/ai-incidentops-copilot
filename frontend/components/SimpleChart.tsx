export function BarList({ data, valueKey = "value", nameKey = "name" }: { data: Array<Record<string, string | number>>; valueKey?: string; nameKey?: string }) {
  const max = Math.max(1, ...data.map((item) => Number(item[valueKey] || 0)));
  return (
    <div className="space-y-3">
      {data.map((item) => {
        const value = Number(item[valueKey] || 0);
        return (
          <div key={String(item[nameKey])} className="grid grid-cols-[96px_1fr_40px] items-center gap-3 text-sm">
            <span className="truncate text-muted">{item[nameKey]}</span>
            <div className="h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-500" style={{ width: `${Math.max(6, (value / max) * 100)}%` }} />
            </div>
            <span className="text-right font-medium text-ink">{value}</span>
          </div>
        );
      })}
    </div>
  );
}

export function TrendBars({ data }: { data: Array<{ date: string; count: number }> }) {
  const max = Math.max(1, ...data.map((item) => item.count));
  return (
    <div className="flex h-48 items-end gap-3">
      {data.map((item) => (
        <div key={item.date} className="flex flex-1 flex-col items-center gap-2">
          <div className="flex h-36 w-full items-end rounded-md bg-slate-100 px-2">
            <div className="w-full rounded-t-md bg-cyan-500" style={{ height: `${Math.max(8, (item.count / max) * 100)}%` }} />
          </div>
          <span className="text-xs text-muted">{item.date}</span>
        </div>
      ))}
    </div>
  );
}
