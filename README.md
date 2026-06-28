# 智维工单 / AI IncidentOps Copilot

AI IncidentOps Copilot 是一个面向 IT 运维与安全场景的智能工单平台作品集。项目采用 Next.js、FastAPI 与 SQLite 构建，支持工单提交、附件处理、任务流转、人工复核、分析记录和数据看板，并提供默认离线可运行、证据驱动、可测试的分析工作流。

项目使用合成种子数据与测试夹具基准集进行演示与回归验证，不包含真实企业数据。相关评估结果用于验证离线工作流与证据引用规则，不代表线上业务效果。

## 当前实现能力

- 文本、日志、截图 OCR 证据提取：从用户描述、运行日志和截图中提取诊断信息，识别 ERROR/WARN、HTTP 4xx/5xx、异常名、timeout/database/unauthorized 等信号。
- PII 脱敏：进入追踪记录（trace）、UI 摘要和分析记录前脱敏邮箱、手机号、Bearer/JWT/API Key、密码、Cookie/Session，可配置内网 IP。
- 本地混合检索（Hybrid Retrieval）：KnowledgeBaseChunk 按边界切块，使用 FAISS 向量检索、BM25 关键词检索、RRF 融合和启发式重排。
- 知识库摄取与版本化：支持 Markdown、TXT、PDF 文档摄取，复用 KnowledgeBaseArticle / KnowledgeBaseChunk，并记录 KBIngestionRun、kb_version、服务提供方和耗时。
- 证据约束分诊：默认 `rule_fallback`，输出分析提供方、`rationale`、`evidence_ids`、`chunk_ids`、`uncertainty` 和人工复核原因。
- 可选 LLM 结构化分析：配置 OpenAI-compatible 服务提供方后，仅基于已脱敏工单摘要和本次检索知识片段生成结构化建议；引用校验失败会回退规则分诊。
- 可回放分析运行：每次分析生成 run_id、trace_id、阶段追踪记录、服务提供方、索引版本、语料哈希、候选来源、最终引用和与上次运行的差异。
- 演示环境访问控制：前端通过演示身份传递 `X-Demo-User-Id`，报障员工仅可访问自己的工单与附件，运维管理员可访问管理端接口；缺少演示身份时，受保护接口返回 401。
- 只读 MCP 工具层：通过 stdio MCP 服务暴露知识检索、工单分析摘要、KB 索引状态和摄取历史查询，复用演示身份权限边界。
- 评估体系：30 条合成基准用例，覆盖负例、冲突例、小图 OCR 路径和 OCR 失败路径，输出检索、分诊、延迟、服务提供方使用等指标，并设置非零质量门槛。

## 架构

```mermaid
flowchart LR
  UI["Next.js 前端"] --> API["FastAPI REST API"]
  MCPC["MCP 客户端"] --> MCPS["MCP 服务（stdio）"]
  MCPS --> API
  API --> DB["SQLite"]
  API --> UP["受控附件存储"]
  API --> PIPE["IncidentAnalysisPipeline"]
  PIPE --> EVID["证据提取：文本 / 日志 / OCR / 脱敏"]
  PIPE --> RET["混合检索：FAISS + BM25 + RRF"]
  RET --> KB["KnowledgeBaseArticle + Chunk"]
  PIPE --> TRIAGE["分诊提供方：rule_fallback / 可选 LLM"]
  PIPE --> AUDIT["AIAnalysisAudit：运行记录、追踪记录与证据引用"]
  API --> RBAC["演示 RBAC"]
```

## 演示截图

![知识库摄取状态](docs/images/kb-ingestion-status.png)

![工单分析追踪记录](docs/images/ticket-analysis-trace.png)

## 事件分析流程

```mermaid
flowchart TD
  A["输入校验与权限检查"] --> B["附件读取与 PII 脱敏"]
  B --> C["文本 / 日志 / OCR 证据提取"]
  C --> D["基于规则的预分类"]
  D --> E["向量检索与 BM25 候选召回"]
  E --> F["RRF 融合"]
  F --> G["候选结果去重"]
  G --> H["启发式重排 / 跳过重排"]
  H --> I["证据阈值判断"]
  I --> J["证据约束最终分诊"]
  J --> K["引用知识库证据生成处置建议"]
  K --> L["风险策略与人工复核决策"]
  L --> M["持久化分析运行与追踪记录"]
```

每个阶段保存服务提供方、耗时、状态、输入/输出摘要和错误信息。高危、安全类、低证据、OCR 失败、低置信度会进入人工复核。

## 混合检索

1. 知识库文章被切为约 520 字符的知识片段，保留约 80 字符重叠内容。
2. 分词器保留中文词、英文词、HTTP 状态码、异常名、ORA/SQLSTATE、ECONNRESET 等诊断 token。
3. 向量召回默认使用本地 hash embedding + FAISS。
4. 关键词召回使用 BM25。
5. RRF 融合后进行去重和启发式重排。
6. 返回知识片段级证据摘录、`dense_score`、`lexical_score`、`fusion_score`、`rerank_score`、`final_score`。

## 知识库摄取与索引

支持 Markdown、文本和 PDF 文档摄取。文件经过上传校验、文本提取、文档标准化、分块、元数据绑定、向量索引与关键词索引构建后进入版本化知识库；每次摄取均记录状态、耗时、服务提供方、模型名、降级原因和 KB 版本。

摄取命令：

```bash
cd backend
.venv/bin/python -m app.scripts.ingest_kb --source tests/fixtures/kb_sample.md
.venv/bin/python -m app.scripts.ingest_kb --source tests/fixtures/kb_sample.pdf
.venv/bin/python -m app.scripts.ingest_kb --check
```

管理员也可以通过 `POST /api/kb/ingest` 上传 `.md`、`.txt`、`.pdf` 文件。原始知识库文件保存在受控上传目录，不通过公开静态目录暴露。

## 语义检索与混合检索

系统支持 SentenceTransformer 语义检索与本地 hash 降级回退（fallback）。默认配置使用 `local_hash_embedding_fallback`，CI、Docker 和离线测试不会下载模型；显式设置 `EMBEDDING_PROVIDER=sentence_transformers` 并安装 `requirements-optional.txt` 后，系统会尝试加载 `SENTENCE_TRANSFORMER_MODEL` 指定的模型。模型下载、加载或推理失败时会回退到 hash fallback，并在摄取运行记录、索引清单、API 响应和页面中记录原因。

检索可运行于 `bm25_only`、`dense_only` 和 `hybrid_rrf` 三种模式。评估报告会记录实际服务提供方、检索指标和延迟；不会假设混合检索一定优于单路检索。

## 检索评估

项目使用合成回归基准集比较不同检索模式，并输出 HitRate@K、MRR、nDCG@K、EvidencePrecision、UnsupportedCitationRate 和平均延迟。结果用于验证本地工作流，不代表真实企业线上效果。

## 默认离线配置与可选扩展

| 能力 | 默认实现 | 说明 |
| --- | --- | --- |
| OCR | `pytesseract_ocr` | 本地 OCR，就绪状态检查 Python 包、Tesseract 可执行文件与所需语言包；不可用时记录降级状态。 |
| 向量索引 | `local_hash_embedding_fallback` + FAISS | 默认使用可重复的本地向量生成方式构建离线索引。 |
| 关键词检索 | `bm25_lexical` | 基于诊断 token 的本地关键词检索。 |
| 融合 | `rrf_fusion` | 使用 Reciprocal Rank Fusion 融合向量与关键词候选。 |
| 重排 | `heuristic_reranker` | 基于本地规则的候选去重与排序。 |
| 分诊 | `rule_fallback` | 基于证据约束的离线规则分诊与人工复核决策。 |
| 可选扩展 | `sentence_transformers` | 显式配置后可尝试加载；不可用时保留降级原因。 |
| 可选分析 | `openai_compatible` | 显式配置 `ANALYSIS_PROVIDER=openai_compatible`、API Base、模型和 API Key 后启用；输出必须通过 JSON schema 与知识片段引用校验。 |

## MCP 工具接口

项目通过只读 MCP 服务暴露受控的运维知识检索、工单分析、知识库状态和摄取历史工具。MCP 工具复用现有检索、版本和演示权限边界，不提供写入、自动执行或工单状态修改能力。

启动方式：

```bash
cd backend
MCP_DEMO_USER_ID=7 .venv/bin/python -m app.mcp_server
```

`MCP_DEMO_USER_ID` 必须显式配置。未配置时工具默认拒绝访问；报障员工只能读取自己有权访问的工单，运维管理员才能读取 KB 索引状态和摄取历史。这是演示身份机制，不代表生产认证。

可用只读工具：

- `search_incident_knowledge(query, top_k, retrieval_mode)`：复用现有 BM25 / 向量 / 混合 RRF 检索，返回知识片段证据、服务提供方、模型和降级状态。
- `get_ticket_analysis(ticket_id)`：返回已脱敏的工单摘要、当前分析结论、引用知识片段、追踪记录摘要和复核原因。
- `get_kb_index_status()`：返回 KB 版本、知识库文章 / 知识片段数量、服务提供方、模型、降级状态、最近摄取和重建时间，要求运维管理员演示身份。
- `list_ingestion_runs(limit)`：返回最近摄取记录，要求运维管理员演示身份。

基于 stdio 的 MCP 客户端可使用如下配置形式：

```json
{
  "mcpServers": {
    "incidentops": {
      "command": "/absolute/path/to/backend/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/backend",
      "env": {
        "MCP_DEMO_USER_ID": "7"
      }
    }
  }
}
```

## 可选 LLM 结构化分析

默认系统使用离线规则分诊。配置 OpenAI-compatible 服务提供方后，系统会基于已脱敏的工单信息和本次检索出的知识库证据生成结构化分析结果。

```bash
ANALYSIS_PROVIDER=openai_compatible
OPENAI_API_BASE=https://api.example.com/v1
OPENAI_MODEL=your-model-name
OPENAI_API_KEY=your-api-key
LLM_ANALYSIS_TIMEOUT_SECONDS=30
LLM_ANALYSIS_MAX_EVIDENCE_CHUNKS=8
```

模型输出必须符合结构化 JSON schema：`category`、`severity`、`summary`、`recommended_actions`、`cited_chunk_ids`、`confidence`、`review_reason`。`cited_chunk_ids` 必须引用本次检索候选中的 `chunk_id`；JSON、字段、置信度或引用校验失败时，系统会自动回退至规则分诊，并将原因记录在分析运行记录中。

回退条件包括：`missing_api_key`、`timeout`、`provider_error`、`invalid_json`、`invalid_schema`、`invalid_citation`。回退后工单分析继续完成，分析提供方记录为 `rule_fallback`，追踪记录标记降级，并进入人工复核策略。

## 数据处理与演示访问控制

- 原附件保存在受控上传目录，不再通过公开静态目录暴露。
- 附件下载走 `GET /api/tickets/{ticket_id}/attachments/{attachment_id}/download` 并进行访问控制。
- 进入分析追踪记录、日志、检索 query、UI 摘要的内容默认执行 PII 脱敏。
- 当前访问控制采用演示身份，用于展示身份边界、附件访问限制和越权测试；生产环境可替换为 OIDC/JWT 等认证方案。
- 前端会自动把当前演示身份写入 `X-Demo-User-Id` 请求头；使用 curl、Postman 或脚本直接访问受保护 API 时，需要手动带上该请求头，例如 `X-Demo-User-Id: 1` 或 `X-Demo-User-Id: 7`。

## 数据库与迁移

```bash
cd backend
.venv/bin/alembic upgrade head
```

旧 SQLite 升级使用 Alembic 补字段。重置演示数据会清空演示表：

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed --reset
```

## 本地运行

```bash
# 后端
cd backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed --reset
.venv/bin/python -m uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

默认 `requirements.txt` 不安装 `sentence-transformers`，Docker 和 CI 使用本地 hash embedding fallback。需要实验可选 SentenceTransformer 时再执行：

```bash
cd backend
.venv/bin/python -m pip install -r requirements-optional.txt
EMBEDDING_PROVIDER=sentence_transformers .venv/bin/python -m app.scripts.ingest_kb --rebuild
```

访问：

- 前端：http://localhost:3000
- API：http://localhost:8000/api/health/ready

如果本机 3000 端口已被占用，可临时使用：

```bash
FRONTEND_PORT=3001 docker compose up --build
```

## Docker

```bash
docker compose up --build
```

后端镜像会安装 Tesseract OCR、英文和简体中文语言包，并在启动前执行 `alembic upgrade head`。默认 compose 文件显式设置 `OCR_REQUIRED_LANGUAGES=eng,chi_sim` 和 `BOOTSTRAP_DEMO_DATA=true`，仅用于本地演示：首次启动时会在迁移完成后导入合成演示数据并重建本地 KB 索引。普通部署应关闭演示数据初始化，并用显式 seed / ingest 命令管理演示数据。

`GET /api/health/ready` 会真实探测 OCR 状态：`pytesseract` Python 包、Tesseract 可执行文件、已安装语言、必需语言、就绪状态和降级原因。OCR 不可用时接口仍返回 200，但整体 `status` 为 `degraded`，表示服务可运行但截图 OCR 会降级。

## 本地端到端演示

### 启动环境

从项目根目录启动：

```bash
export FRONTEND_PORT=3001
docker compose up -d --build
docker compose ps
```

Docker Desktop 必须先启动。启动后访问：

- 前端地址：http://localhost:3001
- 后端 API：http://localhost:8000

`docker compose ps` 中 backend 应显示 `healthy`，frontend 应显示运行中。

### 角色入口

| 角色 | 页面入口 | 权限 |
| --- | --- | --- |
| 报障员工 A | `/requester/dashboard` | 仅查看和提交自己的工单 |
| 运维管理员 | `/admin/dashboard` | 查看全部工单、分析记录、复核和统计 |

身份切换后会自动跳转到对应角色首页；这是本地 Demo RBAC，不是生产级认证。

### 创建 VPN 日志文件

在本机创建可上传的 UTF-8 `.log` 文件：

```bash
cat > ~/Desktop/incidentops-demo-vpn.log <<EOF
$(date -u +"%Y-%m-%dT%H:%M:%SZ") ERROR vpn-client connection timeout
gateway=vpn.corp.example.com
user=demo.employee@example.com
Authorization: Bearer demo-token-for-redaction-test
password=demo-password-for-redaction-test
message=Unable to establish VPN tunnel after network switch
EOF
```

### 报障员工提交工单

以“报障员工 A”进入：

```text
/requester/tickets/new
```

填写：

```text
标题：
企业 VPN 连接超时，无法访问内部系统

问题描述：
今天远程办公时无法连接企业 VPN。切换家庭网络后仍然提示连接超时，导致无法访问内部系统。请协助排查网关连接、账号权限和客户端配置。

类别：
网络连接

紧急程度：
高

受影响系统：
企业 VPN

联系邮箱：
demo.employee@example.com

日志文件：
~/Desktop/incidentops-demo-vpn.log
```

预期结果：

- 显示网络连接、高风险；
- 记录显示浏览器本地时间；
- 邮箱、Bearer Token、password 被脱敏；
- 展示知识库证据、检索来源、分析运行记录和 Trace；
- 高风险工单进入人工复核。

### 运维管理员查看与复核

1. 切换到运维管理员，或进入 `/admin/tickets`。
2. 搜索 `企业 VPN 连接超时`。
3. 打开最新工单。
4. 查看脱敏日志、知识库来源、混合检索、运行 ID、Trace 和人工复核原因。
5. 进入 `/admin/ai-review`。
6. 填写复核备注并点击“通过建议”。

示例备注：

```text
已核对 VPN 日志和知识库证据。建议先检查 VPN 客户端、证书、网络出口和网关日志；同意按“网络连接 / 高优先级”处理。
```

通过后，待复核数量减少，已通过数量增加。

### 可选：恢复种子数据

> 警告：`python -m app.seed --reset` 会清空当前工单、附件、分析运行和复核记录；它不属于日常启动或展示步骤，仅在明确需要完全重新初始化时使用。

### 停止环境

```bash
docker compose down
```

## 测试与评估

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python -m app.scripts.ingest_kb --check
.venv/bin/python -m app.scripts.evaluate

cd ../frontend
npm run test
npm run lint
npm run build
```

评估输出：

- `artifacts/evaluation_report.json`
- `artifacts/evaluation_report.md`

当前评测集为合成回归基准集，用于检查检索、引用和人工复核规则是否发生退化。分类类指标反映固定测试夹具上的一致性；EvidencePrecision 与 UnsupportedCitationRate 用于识别证据引用质量问题。

## API 摘要

受保护 API 均使用演示身份头 `X-Demo-User-Id` 做演示 RBAC。缺少该 header 会返回 401；报障员工与运维管理员的访问范围由演示身份决定。

- Tickets: `GET /api/tickets`, `POST /api/tickets`, `GET /api/tickets/{id}`, `PATCH /api/tickets/{id}`, `POST /api/tickets/{id}/reanalyze`
- Users: `GET /api/users`, `GET /api/users/{id}`，仅运维管理员演示身份可访问
- Analysis Runs: `GET /api/tickets/{id}/analysis-runs`, `GET /api/tickets/{id}/analysis-runs/{run_id}`, `GET /api/tickets/{id}/analysis-runs/{run_id}/trace`
- Attachments: `POST /api/tickets/{id}/attachments`, `GET /api/tickets/{id}/attachments/{attachment_id}/download`
- KB: `GET /api/kb`, `POST /api/kb/search`, `POST /api/kb/ingest`, `GET /api/kb/ingestions`, `GET /api/kb/evaluation/summary`, `GET /api/kb/index/status`, `POST /api/kb/index/rebuild`
- AI Review: `GET /api/ai/reviews`, `PATCH /api/ai/reviews/{id}`
- Health: `GET /api/health/live`, `GET /api/health/ready`, `GET /api/system/status`

## 演示路径

1. `/` 查看项目边界和真实 API 数据状态。
2. `/requester/tickets/new` 提交带日志的工单。
3. `/admin/tickets/{id}` 查看证据、知识片段来源、分析流程追踪记录和历史运行记录。
4. `/admin/ai-review` 查看复核原因并覆盖判断。
5. `/requester/kb` 查看索引状态和知识库文章。
6. `/admin/analytics` 查看统计。

## 后续规划

- 增加 CrossEncoder 重排器，并在评估中单独标记。
- 接入 Vision LLM 或更可靠 OCR pipeline。
- 替换演示 RBAC 为 OIDC/JWT。
- 使用 PostgreSQL + pgvector 或 Milvus/Qdrant 替换本地 FAISS。
