import { AppShell } from "@/components/AppShell";
import { serverFetch } from "@/lib/server-api";
import type { KnowledgeBaseArticle } from "@/types";

export const dynamic = "force-dynamic";

interface IndexStatus {
  status: string;
  ready: boolean;
  stale: boolean;
  chunk_count: number;
  manifest?: {
    corpus_hash?: string;
    provider?: string;
    rebuilt_at?: string;
    index_version?: string;
    chunk_count?: number;
    chunking_config?: Record<string, unknown>;
  };
}

export default async function KnowledgeBasePage() {
  const [articles, index] = await Promise.all([
    serverFetch<KnowledgeBaseArticle[]>("/api/kb"),
    serverFetch<IndexStatus>("/api/kb/index/status")
  ]);

  return (
    <AppShell mode="requester" title="知识库" subtitle="常见 IT 与安全事件的标准处置文章">
      <div className="mb-5 rounded-lg border border-line bg-white p-5 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-cyan-700">本地混合检索索引</p>
            <h2 className="mt-1 text-xl font-semibold text-ink">{index.ready ? "索引可用" : "索引需要重建"}</h2>
            <p className="mt-2 text-sm text-muted">
              提供方：{index.manifest?.provider || "local_hash_embedding_fallback"} · 知识片段：{index.chunk_count} · 状态：{index.status === "ready" ? "可用" : "需重建"}
            </p>
          </div>
          <span className={index.ready ? "rounded-md bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700" : "rounded-md bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-700"}>
            {index.ready ? "可用" : "需重建"}
          </span>
        </div>
        <div className="mt-4 grid gap-3 text-xs text-muted md:grid-cols-3">
          <span className="break-all">语料哈希：{index.manifest?.corpus_hash || "-"}</span>
          <span>索引版本：{index.manifest?.index_version || "-"}</span>
          <span>构建时间：{index.manifest?.rebuilt_at || "-"}</span>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {articles.map((article) => (
          <article key={article.id} className="rounded-lg border border-line bg-white p-5 shadow-soft">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-cyan-700">{article.category}</p>
                <h2 className="mt-2 text-lg font-semibold text-ink">{article.title}</h2>
              </div>
              <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-muted">{article.reading_time} 分钟</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted">{article.summary}</p>
            <p className="mt-4 line-clamp-4 text-sm leading-6 text-slate-700">{article.content}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {article.tags.map((tag) => (
                <span key={tag} className="rounded-md bg-violet-50 px-2 py-1 text-xs font-medium text-violet-700">
                  {tag}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </AppShell>
  );
}
