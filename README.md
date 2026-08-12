# 企业智能知识库问答系统（RAG + Agent + FastAPI）

基于 **FastAPI + PostgreSQL/pgvector + RAG + Tool Calling** 实现的企业知识库智能问答项目。

项目面向企业内部文档检索场景，支持知识文件在线管理、Embedding 向量检索、Reranker 精排、Agent 工具调用、多轮上下文、来源追踪和 SSE 流式回答，并提供基础自动化测试与 RAG 端到端评测能力。

本项目的核心 RAG 与 Agent 链路采用原生方式实现，主要用于理解和实践 Embedding、向量召回、Reranker、Tool Calling、上下文组装与流式响应等 AI 应用核心流程。

---

## 一、核心功能

### 1. 用户认证与会话管理

- 用户注册与登录
- bcrypt 密码哈希
- JWT 身份认证
- 多会话聊天记录持久化
- 历史会话查询与删除
- 最近历史消息窗口，为多轮对话提供上下文

### 2. 企业知识库管理

支持在线上传：

- TXT
- Markdown
- 文本型 PDF
- DOCX

上传后的文件会依次完成：

```text
文件上传
→ 文件类型与大小校验
→ 文本解析
→ Chunk 切分
→ Embedding
→ PostgreSQL + pgvector 入库
```

每个 Chunk 保存：

```text
source
file_type
chunk_index
```

用于知识来源追踪。

DOCX额外支持顶层段落与表格按原始顺序提取，并针对可识别章节标题进行章节切分；未识别到章节结构时自动回退普通文本切分。

同名文件重新上传时，旧 Chunk 删除与新 Chunk 写入位于同一数据库事务中；只有全部新向量写入成功后才提交，异常时统一 rollback。

### 3. 两阶段 RAG 检索

核心检索链路：

```text
用户问题
      ↓
Query Rewrite
      ↓
Embedding
      ↓
PostgreSQL + pgvector Top-K 粗召回
      ↓
Reranker 精排
      ↓
relevance_score 阈值过滤
      ↓
恢复完整原始 Chunk
      ↓
拼接来源信息
      ↓
交给 LLM 生成回答
```

当前默认配置：

- Embedding：`BAAI/bge-m3`
- 向量维度：1024
- Reranker：`BAAI/bge-reranker-v2-m3`
- 向量距离：Cosine Distance
- 粗召回数量：Top 10
- Reranker Top-N：3
- 默认相关度阈值：0.25

为了控制外部 Reranker 请求体大小，精排阶段只发送候选 Chunk 的截断文本；获得 Reranker 返回的原始候选 `index` 后，再映射回数据库召回阶段保存的完整 Chunk。

### 4. RAG 降级策略

项目针对 Reranker 不稳定或阈值过严设计了基础降级机制：

```text
正常情况
→ Reranker 精排并筛选高相关 Chunk

精排存在结果但全部低于阈值
→ 保留 Reranker Top1 作为弹性兜底

Reranker Timeout / 请求异常 / 返回异常
→ 回退 PGVector 粗召回 Top3
```

Reranker作为检索增强组件发生故障时，不直接让整条知识检索链路失效。

### 5. Agent 与 Tool Calling

当前 Agent 提供两个工具：

```text
search_knowledge_base
→ 企业知识库 RAG 检索

get_realtime_weather
→ 实时天气查询
```

对话链路：

```text
用户问题
      ↓
读取聊天历史
      ↓
Query Rewrite
      ↓
LLM 进行 Tool Calling 决策
      ↓
执行 RAG Tool / Weather Tool
      ↓
Tool Result 以 role="tool" 加入上下文
      ↓
LLM 基于工具结果生成最终回答
      ↓
SSE 流式返回前端
```

为了降低模型绕过企业知识库直接使用预训练知识回答的风险，在 Prompt 约束之外增加了代码级 RAG 兜底：当模型未返回 Tool Call 时，代码会构造 `search_knowledge_base` 调用。

### 6. SSE 流式响应

聊天接口基于 FastAPI `StreamingResponse` 返回 SSE 数据。

前端逐段读取：

```text
data: {"content": "..."}
```

流结束后返回：

```text
data: [DONE]
```

同时记录：

- 首 Token 延迟（TTFB）
- 总响应耗时
- 使用模型
- 用户 ID

助手最终完整回答会在流结束后通过新的数据库 Session 写入聊天历史。

### 7. RAG 评测

项目包含独立的 `evaluation/` 目录：

```text
evaluation/
├── fixtures_manifest.md
├── rag_evaluation_questions.csv
├── rag_baseline_results.csv
└── run_rag_baseline.py
```

固定评测资料覆盖：

- TXT
- Markdown
- 普通 DOCX
- 表格 DOCX
- 多页 PDF

评测问题覆盖：

- 单文件事实检索
- 精确数字 / 编号 / 命令
- 跨 Chunk 信息
- 多文件相似字段消歧
- 同名章节消歧
- 多轮 Query Rewrite
- 知识库外问题拒答

评测脚本会记录：

- HTTP 状态
- 最终回答
- 返回来源
- 必需关键词覆盖率
- 禁止关键词
- 来源命中
- 拒答结果
- 总响应耗时

由于模型、Prompt、检索参数和代码持续变化，历史 baseline 仅用于版本对比，不代表当前版本固定效果。

---

## 二、技术栈

### Backend

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 Async
- asyncpg
- PostgreSQL
- pgvector
- Pydantic Settings

### AI / RAG

- OpenAI Compatible API
- DeepSeek-V3
- BAAI/bge-m3
- BAAI/bge-reranker-v2-m3
- Query Rewrite
- RAG
- Tool Calling
- SSE

### Engineering

- httpx
- JWT / PyJWT
- bcrypt
- Loguru
- python-multipart
- pypdf
- python-docx

### Frontend

- HTML
- CSS
- JavaScript
- marked.js

---

## 三、项目结构

```text
ai_rag_project/
├── clients/
│   └── llm_client.py
│
├── routers/
│   ├── auth.py
│   ├── chat.py
│   └── knowledge.py
│
├── services/
│   ├── agent_service.py
│   ├── auth_service.py
│   ├── knowledge_service.py
│   └── memory_service.py
│
├── tools/
│   ├── rag_tool.py
│   └── weather_tool.py
│
├── utils/
│   ├── background_tasks.py
│   ├── exception_handlers.py
│   ├── logger.py
│   └── text_splitter.py
│
├── tests/
│   ├── fixtures/
│   ├── test_docx_section_chunking.py
│   ├── test_docx_table_extraction.py
│   ├── test_exception_handlers.py
│   └── test_text_pdf_parsing.py
│
├── evaluation/
│   ├── fixtures_manifest.md
│   ├── rag_evaluation_questions.csv
│   ├── rag_baseline_results.csv
│   └── run_rag_baseline.py
│
├── config.py
├── database.py
├── main.py
├── models.py
├── schemas.py
├── security.py
├── web_ui.html
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 四、核心数据模型

当前主要包含三类数据：

### User

保存用户账号：

```text
id
username
hashed_password
created_at
```

### Document

保存企业知识库 Chunk：

```text
id
content
embedding Vector(1024)
metadata_info JSONB
created_at
```

### ChatMessage

保存聊天记录：

```text
id
user_id
session_id
role
content
created_at
```

---

## 五、主要 API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 登录并获取 JWT |
| POST | `/api/chat/completions` | SSE 流式 AI 对话 |
| GET | `/api/chat/sessions` | 获取历史会话 |
| GET | `/api/chat/history/{session_id}` | 获取指定会话消息 |
| DELETE | `/api/chat/sessions/{session_id}` | 删除会话 |
| POST | `/api/knowledge/upload` | 上传知识文件 |
| GET | `/api/knowledge/documents` | 获取知识库文件列表 |
| DELETE | `/api/knowledge/documents/{file_name}` | 删除知识文件 |

---

## 六、本地运行

### 1. 环境要求

建议：

```text
Python >= 3.11
PostgreSQL >= 14
PostgreSQL 已安装 pgvector 扩展
```

同时需要能够访问配置的大模型、Embedding、Reranker以及天气服务。

### 2. 克隆仓库

```bash
git clone https://github.com/yangmingzhou2759678997/ai_rag_project.git
cd ai_rag_project
```

### 3. 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 配置环境变量

在项目根目录创建 `.env`。

示例：

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
ENVIRONMENT=development
LOG_LEVEL=INFO

OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
CHAT_MODEL=your_chat_model
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=1024

EMBEDDING_MODEL=BAAI/bge-m3
VECTOR_DIMENSION=1024
CHUNK_SIZE=350
CHUNK_OVERLAP=50
RECALL_TOP_K=10
RERANK_TOP_K=3
RERANK_SCORE_THRESHOLD=0.25

RERANKER_API_URL=https://your-reranker-endpoint/v1/rerank
RERANKER_API_KEY=your_reranker_api_key
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=ai_rag
DATABASE_URL=postgresql+asyncpg://postgres:your_password@127.0.0.1:5432/ai_rag

SECRET_KEY=replace_with_a_random_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> `.env` 包含数据库密码、API Key 和 JWT Secret，不应提交到 Git。

生成随机 JWT Secret：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 6. 启用 pgvector

连接目标 PostgreSQL 数据库后执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

FastAPI 启动时会通过 SQLAlchemy `create_all` 创建当前不存在的数据表。

当前项目未使用 Alembic，因此数据库 Schema 发生正式版本变化时，需要额外处理迁移。

### 7. 启动后端

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

开发环境可使用：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

打开：

```text
http://127.0.0.1:8000/docs
```

即可查看 FastAPI Swagger API 文档。

### 8. 启动前端

另开终端：

```bash
python -m http.server 3000
```

浏览器访问：

```text
http://127.0.0.1:3000/web_ui.html
```

`web_ui.html` 默认后端地址：

```javascript
const BACKEND_BASE_URL = "http://localhost:8000";
```

如果后端运行在其他服务器，需要修改该地址。

---

## 七、知识库使用方式

登录系统后，可直接通过前端上传知识文件。

支持：

```text
.txt
.md
.pdf
.docx
```

默认最大文件大小为 10 MB。

PDF当前依赖 `pypdf` 提取文字层，因此扫描图片型PDF无法直接解析，需要额外OCR能力。

同名文件再次上传时，会替换数据库中该文件已有的知识 Chunk。

---

## 八、运行测试

安装依赖后：

```bash
pytest -q
```

也可以分别运行：

```bash
pytest -q tests/test_text_pdf_parsing.py
pytest -q tests/test_docx_section_chunking.py
pytest -q tests/test_docx_table_extraction.py
pytest -q tests/test_exception_handlers.py
```

测试重点覆盖文档文本提取、Chunk切分、DOCX表格顺序、章节处理和异常响应。

---

## 九、运行 RAG 评测

首先确保：

- FastAPI 后端已经运行；
- 测试账号已经注册；
- 固定评测资料已经上传至知识库。

然后执行：

```bash
python evaluation/run_rag_baseline.py
```

也可只运行指定题目：

```bash
python evaluation/run_rag_baseline.py --questions Q001,Q024,Q038
```

程序会交互式获取登录信息，并把结果写入：

```text
evaluation/rag_baseline_results.csv
```

登录密码仅在程序运行期间使用，不写入评测结果文件。

---

## 十、设计说明

### 为什么主项目没有使用 LangChain？

本项目的核心RAG与Agent链路选择直接使用OpenAI兼容API、SQLAlchemy和pgvector实现，主要目的是完整理解：

```text
Embedding
→ Retriever
→ Reranker
→ Context
→ Tool Calling
→ Tool Result
→ Final Answer
```

而不是把底层流程全部交给框架封装。

在此基础上，可再通过LangChain实践对照Model、Retriever、Tool和Agent等抽象与原生实现之间的关系。

### 为什么使用向量召回 + Reranker？

PGVector主要负责从知识库中快速取得候选集合，Reranker再针对“当前问题与候选文本”的相关性进行二次排序。

两阶段检索将：

```text
Recall
```

与：

```text
Ranking
```

拆开处理，使检索链路更容易调试和优化。

---

## 十一、当前边界

当前项目定位为AI应用开发与求职展示项目，不等同于完整企业生产系统。

目前主要边界包括：

- PDF仅支持带文字层文件，不包含OCR；
- 知识库为系统共享知识库，尚未实现用户级知识空间隔离；
- 数据库Schema目前通过`create_all`管理，未接入Alembic；
- 检索以向量召回为主，尚未加入BM25等混合检索；
- 前端为原生HTML / CSS / JavaScript实现，重点在AI后端链路；
- 生产环境仍应进一步收紧CORS、完善监控与部署策略。

---

## 十二、安全说明

请勿提交：

```text
.env
API Key
数据库密码
JWT Secret
日志中的敏感信息
```

项目`.gitignore`已忽略`.env`、虚拟环境、Python缓存、日志及IDE配置。

如果密钥曾进入公开仓库，应立即撤销并重新生成。

---

## 十三、项目定位

这是一个围绕企业知识库场景构建的个人AI应用项目。

重点不是训练大模型，而是完成：

```text
大模型API集成
+
Python异步后端
+
RAG检索
+
Agent工具调用
+
知识库管理
+
测试与评测
```

并通过实际代码理解企业AI应用从“模型调用”走向“可检索、可追踪、可调试应用”的完整过程。