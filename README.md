# 企业知识库智能问答系统（RAG + Agent + FastAPI）

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green)](https://fastapi.tiangolo.com/)
[![PGVector](https://img.shields.io/badge/PGVector-0.4.2-orange)](https://github.com/pgvector/pgvector)

基于 FastAPI、PostgreSQL、PGVector、RAG 与大模型 Function Calling 实现的企业知识库问答项目。当前支持用户注册登录、多会话管理、聊天记录持久化、知识库检索、天气工具调用和 SSE 流式输出。

> 当前版本为本地学习与求职展示项目，尚未部署到生产环境。知识库数据目前通过 `seed_db.py` 从固定 TXT 文件离线导入，文件上传和多格式解析属于后续优化项。

## 一、项目目标

通用大模型无法直接访问企业私有资料，并可能生成缺乏依据的回答。本项目通过检索增强生成（RAG）和工具调用机制，在回答企业知识问题前检索内部知识库，并将检索结果作为上下文交给大模型生成答案。

## 二、当前功能

### 1. 用户认证

- 用户注册与用户名唯一性校验
- bcrypt 密码哈希存储
- JWT 登录认证
- 受保护接口通过 FastAPI 依赖注入获取当前用户

### 2. 多会话与聊天记忆

- 使用 `session_id` 区分不同会话
- 聊天消息持久化到 PostgreSQL
- 加载最近的历史消息作为多轮对话上下文
- 查询和删除当前用户的历史会话

### 3. RAG 检索链路

当前知识库链路为：

```text
TXT 文档
→ 段落优先与固定长度结合的文本切分
→ Embedding 向量化
→ PostgreSQL + PGVector 存储
→ Top-K 向量召回
→ Reranker 重排序
→ 分数阈值过滤与异常降级
→ 将高相关文本交给大模型生成回答
```

其中：

- Embedding 模型：`BAAI/bge-m3`
- 向量维度：1024
- Reranker：`BAAI/bge-reranker-v2-m3`
- 向量检索：PGVector 余弦距离排序

### 4. Agent 工具调用

项目使用大模型 Function Calling，根据问题选择并调用后端工具：

- `search_knowledge_base`：检索企业知识库
- `get_realtime_weather`：查询指定城市天气

工具调用结果会以 `role="tool"` 消息加入上下文，再由大模型生成最终回答。对于非寒暄问题，代码提供知识库检索兜底，降低模型绕过知识库直接回答的概率。

### 5. SSE 流式响应

- FastAPI 后端以 SSE 格式逐段返回模型内容
- HTML/JavaScript 前端读取响应流并实时渲染
- 对话完成后保存助手回复
- 后台记录总耗时和首 Token 延迟

### 6. 工程基础

- SQLAlchemy 异步数据库访问
- 全局异常处理
- 接口限流
- 日志记录与日志轮转
- 数据库事务提交与回滚
- CORS 配置

## 三、技术栈

### 后端

- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- PGVector
- asyncpg
- Pydantic Settings

### 大模型与检索

- OpenAI 兼容 API
- DeepSeek / 硅基流动
- BAAI/bge-m3
- BAAI/bge-reranker-v2-m3
- Function Calling
- SSE

### 安全与工程组件

- JWT
- bcrypt
- Loguru
- SlowAPI
- httpx

### 前端

- HTML
- CSS
- JavaScript

## 四、项目结构

```text
ai_rag_project/
├── clients/
│   └── llm_client.py
├── routers/
│   ├── auth.py
│   └── chat.py
├── services/
│   ├── agent_service.py
│   ├── auth_service.py
│   └── memory_service.py
├── tools/
│   ├── rag_tool.py
│   └── weather_tool.py
├── utils/
│   ├── background_tasks.py
│   ├── exception_handlers.py
│   ├── logger.py
│   ├── rate_limiter.py
│   └── text_splitter.py
├── data/
│   └── company_knowledge.txt
├── config.py
├── database.py
├── main.py
├── models.py
├── schemas.py
├── security.py
├── seed_db.py
├── web_ui.html
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 五、运行环境

- Python 3.10～3.12
- PostgreSQL 14+
- PostgreSQL 已安装 PGVector 扩展
- 可以访问配置的大模型、Embedding 和 Reranker API

## 六、安装与配置

### 1. 克隆项目

```bash
git clone https://github.com/yangmingzhou2759678997/ai_rag_project.git
cd ai_rag_project
```

### 2. 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows CMD：

```bat
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 创建本地环境变量文件

Windows：

```bat
copy .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

编辑 `.env`，填入真实的 API Key、数据库连接信息和 JWT 密钥。

安全要求：

- 不要把 `.env` 提交到 Git
- 不要在 README、截图或日志中暴露真实密钥
- 如果密钥曾经公开或上传，应立即撤销并生成新密钥
- `DATABASE_URL` 中的特殊字符密码需要进行 URL 编码

生成 JWT 随机密钥：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 七、数据库准备

在 PostgreSQL 中创建数据库，并启用 PGVector：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

应用启动时，FastAPI `lifespan` 会根据 ORM 模型创建不存在的数据表。

> `create_all` 适用于当前学习项目。后续生产化版本应使用 Alembic 管理数据库迁移。

## 八、初始化知识库

在项目根目录创建：

```text
data/company_knowledge.txt
```

写入用于测试的企业知识文本，然后执行：

```bash
python seed_db.py
```

当前脚本只读取这个 TXT 文件，不支持 PDF、DOCX、Markdown 上传或文档管理。

## 九、启动项目

### 1. 启动后端

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问：

- 后端根地址：`http://127.0.0.1:8000`
- Swagger 文档：`http://127.0.0.1:8000/docs`

### 2. 启动前端静态页面

保持后端运行，在项目根目录另开终端：

```bash
python -m http.server 3000
```

浏览器访问：

```text
http://127.0.0.1:3000/web_ui.html
```

`web_ui.html` 是普通 HTML/JavaScript 页面，不需要 Streamlit。

## 十、核心数据流

```text
前端发送问题和 JWT
→ FastAPI 路由匹配、参数校验和用户认证
→ 加载聊天历史
→ 重写当前问题
→ 大模型判断工具调用
→ 后端执行 RAG 或天气工具
→ 工具结果加入模型上下文
→ 大模型流式生成最终回答
→ SSE 返回前端
→ 保存助手消息
```

## 十一、当前限制

- 只支持固定 TXT 文件离线灌库
- 缺少文档上传、删除、更新和重新索引
- 缺少 PDF、DOCX、Markdown 解析
- 缺少检索评估集和自动化测试
- 尚未提供 Docker 部署
- 尚未实现来源引用
- 尚未通过基线评估验证是否需要混合检索

## 十二、后续优化计划

优先级由高到低：

1. 增加 RAG 测试集与检索评估
2. 增加多文件上传和文档管理
3. 支持 TXT、MD、PDF、DOCX 解析
4. 回答中返回来源文档和片段信息
5. 增加自动化测试
6. 增加 Docker 与 Docker Compose
7. 根据评估结果决定是否加入关键词召回与混合检索
8. 适度接入 LangChain 或 LlamaIndex 的真实组件

## 十三、开发说明

项目开发过程中使用 AI 工具辅助完成部分代码生成、语法查询和问题排查。本人已对核心请求链路、Agent 工具调用、RAG 检索、数据库模型及认证流程进行系统复盘，并持续通过测试和功能优化提升独立开发能力。
