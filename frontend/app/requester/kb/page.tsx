import { AppShell } from "@/components/AppShell";
import { serverFetch } from "@/lib/server-api";
import type { KnowledgeBaseArticle } from "@/types";

export const dynamic = "force-dynamic";

interface IndexStatus {
  status: string;
  ready: boolean;
  stale: boolean;
  kb_version?: string;
  article_count?: number;
  chunk_count: number;
  latest_ingestion_run?: IngestionRun | null;
  manifest?: {
    corpus_hash?: string;
    provider?: string;
    embedding_model?: string;
    fallback_reason?: string | null;
    rebuilt_at?: string;
    index_version?: string;
    chunk_count?: number;
    chunking_config?: Record<string, unknown>;
  };
}

interface IngestionRun {
  id: number;
  status: "pending" | "running" | "completed" | "degraded" | "failed";
  source_filename?: string | null;
  source_type?: string | null;
  document_count: number;
  chunk_count: number;
  embedding_provider: string;
  embedding_model?: string | null;
  kb_version: string;
  started_at: string;
  completed_at?: string | null;
  latency_ms?: number | null;
  fallback_reason?: string | null;
  error_message?: string | null;
}

interface EvaluationSummary {
  available: boolean;
  generated_from: string;
  retrieval_modes: Record<string, {
    "HitRate@1"?: number;
    "HitRate@3"?: number;
    "HitRate@5"?: number;
    MRR?: number;
    "nDCG@3"?: number;
    EvidencePrecision?: number;
    UnsupportedCitationRate?: number;
    avg_latency_ms?: number;
    embedding_provider?: string;
  }>;
}

export default async function KnowledgeBasePage() {
  const [articles, index, ingestions, evaluation] = await Promise.all([
    serverFetch<KnowledgeBaseArticle[]>("/api/kb"),
    serverFetch<IndexStatus>("/api/kb/index/status"),
    serverFetch<IngestionRun[]>("/api/kb/ingestions"),
    serverFetch<EvaluationSummary>("/api/kb/evaluation/summary")
  ]);

  return (
    <AppShell mode="requester" title="知识库" subtitle="常见 IT 与安全事件的标准处置文章">
      <div className="mb-5 rounded-lg border border-line bg-white p-5 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-cyan-700">本地混合检索索引</p>
            <h2 className="mt-1 text-xl font-semibold text-ink">{index.ready ? "索引可用" : "索引需要重建"}</h2>
            <p className="mt-2 text-sm text-muted">
              提供方：{index.manifest?.provider || "local_hash_embedding_fallback"} · 模型：{index.manifest?.embedding_model || "local_hash_embedding_fallback"} · 状态：{index.status === "ready" ? "可用" : "需重建"}
            </p>
          </div>
          <span className={index.ready ? "rounded-md bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700" : "rounded-md bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-700"}>
            {index.ready ? "可用" : "需重建"}
          </span>
        </div>
        <div className="mt-4 grid gap-3 text-xs text-muted md:grid-cols-4">
          <span>KB 版本：{index.kb_version || "-"}</span>
          <span>文章数：{index.article_count ?? articles.length}</span>
          <span>知识片段：{index.chunk_count}</span>
          <span>最近摄取：{index.latest_ingestion_run?.source_filename || "-"}</span>
          <span className="break-all">语料哈希：{index.manifest?.corpus_hash || "-"}</span>
          <span>索引版本：{index.manifest?.index_version || "-"}</span>
          <span>构建时间：{index.manifest?.rebuilt_at || "-"}</span>
          <span>降级原因：{index.manifest?.fallback_reason || "-"}</span>
        </div>
      </div>
      <section className="mb-5 rounded-lg border border-line bg-white p-5 shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-cyan-700">摄取历史</p>
            <h2 className="mt-1 text-lg font-semibold text-ink">最近知识库文件处理记录</h2>
          </div>
          <p className="text-xs text-muted">修改知识库后由管理员触发索引重建。</p>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="py-2">文件</th>
                <th>类型</th>
                <th>状态</th>
                <th>文档 / 片段</th>
                <th>Provider</th>
                <th>KB 版本</th>
                <th>耗时</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {ingestions.length === 0 ? (
                <tr><td colSpan={8} className="py-4 text-muted">暂无摄取记录，当前知识库来自 demo seed 或手动文章。</td></tr>
              ) : ingestions.slice(0, 6).map((run) => (
                <tr key={run.id} className="border-b border-line/70">
                  <td className="py-3 font-medium text-ink">{run.source_filename || "-"}</td>
                  <td>{run.source_type || "-"}</td>
                  <td>{run.status}</td>
                  <td>{run.document_count} / {run.chunk_count}</td>
                  <td>{run.embedding_provider}<br /><span className="text-xs text-muted">{run.embedding_model || "-"}</span></td>
                  <td>{run.kb_version}</td>
                  <td>{run.latency_ms ? `${run.latency_ms} ms` : "-"}</td>
                  <td className="max-w-xs text-xs text-muted">{run.fallback_reason || run.error_message || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="mb-5 rounded-lg border border-line bg-white p-5 shadow-soft">
        <p className="text-sm font-semibold text-cyan-700">检索评估摘要</p>
        <h2 className="mt-1 text-lg font-semibold text-ink">Synthetic regression benchmark</h2>
        {!evaluation.available ? (
          <p className="mt-3 text-sm text-muted">尚未生成评估报告。运行后端命令 `python -m app.scripts.evaluate` 后会展示 BM25、Dense 和 Hybrid RRF 指标。</p>
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {Object.entries(evaluation.retrieval_modes).map(([mode, metrics]) => (
              <div key={mode} className="rounded-md border border-line p-4">
                <p className="font-semibold text-ink">{mode}</p>
                <p className="mt-2 text-xs text-muted">Provider：{metrics.embedding_provider || "-"}</p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-700">
                  <span>Hit@3：{metrics["HitRate@3"] ?? "-"}</span>
                  <span>MRR：{metrics.MRR ?? "-"}</span>
                  <span>nDCG@3：{metrics["nDCG@3"] ?? "-"}</span>
                  <span>平均延迟：{metrics.avg_latency_ms ?? "-"} ms</span>
                  <span>证据精度：{metrics.EvidencePrecision ?? "-"}</span>
                  <span>弱引用率：{metrics.UnsupportedCitationRate ?? "-"}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
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
