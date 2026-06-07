项目简介：基于 FastAPI + PostgreSQL + PGVector + RAG + 智能 Agent 实现的企业内部智能问答系统，支持用户注册登录、多会话对话管理、历史聊天记忆、企业知识库检索、实时天气查询、SSE 流式对话等功能。本项目为个人学习练手项目，完整实现大模型应用落地全流程，已本地测试运行通过。
一、项目背景
传统企业内部文档查询依赖人工翻阅，效率低下；同时通用大模型存在知识幻觉问题，无法精准匹配企业私有数据。
本项目基于检索增强生成（RAG）+ 大模型工具调用（Agent）架构，将企业文档向量化存入向量数据库，结合会话记忆、权限校验、接口限流、全局异常捕获等工程化能力，实现私有知识库问答 + 工具调用一体化智能应用。
二、核心技术栈
后端核心
编程语言：Python 3.10+
Web 框架：FastAPI（异步接口、SSE 流式响应、依赖注入、后台任务）
数据库：PostgreSQL + PGVector（向量存储、余弦相似度检索）
ORM 框架：SQLAlchemy（异步数据库操作、事务管理）
大模型 & 工具链
大模型服务：DeepSeek、硅基流动（兼容 OpenAI 标准 API 协议）
向量模型：BAAI/bge-m3（文本向量化，1024 维向量）
重排模型：BAAI/bge-reranker-v2-m3（检索结果精排）
Agent 能力：大模型 Function Call 工具调用，支持多工具调度
安全 & 工程化组件
身份认证：JWT 令牌、BCrypt 密码加盐哈希加密
日志管理：Loguru（分级日志、控制台 + 文件双输出、日志切割）
接口限流：slowapi（基于客户端 IP 限流，防恶意请求）
异步请求：httpx（异步 HTTP 客户端，调用第三方 API）
异常处理：全局异常捕获、参数校验异常、HTTP 异常统一封装
前端界面
交互界面：Streamlit（轻量化 Web 前端，实现登录、会话管理、流式对话）
三、项目整体架构
项目采用分层模块化架构，代码解耦、职责清晰，分为 路由层 / 服务层 / 工具层 / 数据层 / 通用工具层，整体数据流如下：
前端（Streamlit）发起 HTTP 请求 → 路由层（Routers）接收请求、身份校验、参数校验
路由层调用对应业务服务（Services），处理核心业务逻辑
服务层调用通用工具（Tools / Clients / Utils）、操作数据库（Database / Models）
大模型 / 第三方工具执行完毕后，通过 SSE 流式协议返回结果至前端展示
架构分层说明
plaintext
1. 路由层(routers)：接口入口，负责请求接收、权限校验、路由分发
2. 服务层(services)：核心业务逻辑，对话处理、用户认证、聊天记忆管理、Agent 调度
3. 工具层(tools)：文本切片、RAG 检索、天气查询等功能封装
4. 客户端(clients)：大模型统一客户端封装（单例模式）
5. 数据层：数据库连接、数据表模型、数据校验模型
6. 通用工具层(utils)：日志、异常捕获、接口限流、后台任务等公共能力
四、功能模块详解
1. 用户认证模块
用户注册：校验用户名唯一性，密码加盐哈希加密后存入数据库
用户登录：账号密码校验，签发 JWT 身份令牌
全局身份拦截：所有对话接口强制校验登录状态，未登录禁止访问
2. 会话 & 聊天记忆模块
多会话管理：基于 session_id 区分不同对话窗口
历史会话查询：拉取当前用户所有历史会话，按时间倒序展示
聊天记录持久化：用户提问、大模型回复统一存入数据库
历史记录加载：滑动窗口读取历史对话，拼接上下文实现多轮对话
会话删除：支持单会话及对应所有聊天记录批量删除
3. RAG 知识库模块（核心）
完整实现 文档预处理 → 向量化 → 向量存储 → 粗召回 → 重排序 全链路：
文本切分：语义切片，支持段落分割 + 超长文本强制分片，自带文本重叠防上下文断裂
文本向量化：调用 Embedding 模型，将文本转为 1024 维向量
向量检索：基于 PGVector 余弦相似度做粗召回（Top-K）
结果重排：调用 Reranker 模型对召回结果精排，提升检索准确率
多级兜底策略：针对重排超时、分数阈值过严等异常做降级处理
4. 智能 Agent 工具调用模块
基于大模型 Function Call 实现工具自动选择，内置两大工具：
search_knowledge_base：企业知识库检索（核心工具，非寒暄类问题强制调用）
get_realtime_weather：实时天气查询（仅天气相关问题可调用）
双重防护机制：系统提示词约束 + 代码级兜底，杜绝大模型幻觉、规避不调用工具问题
5. 流式对话模块
基于 SSE（Server-Sent Events）实现打字机流式输出
后台异步任务：对话结束后异步统计接口耗时、TTFB 首字延迟、记录运行日志
统一响应格式，前端逐段渲染对话内容
6. 工程化防护能力
全局异常捕获：区分 HTTP 异常、参数校验异常、系统未知异常，统一返回友好提示，不暴露底层报错
接口限流：基于访问 IP 限制请求频次，防护高并发 / 恶意请求
分级日志：INFO/ERROR 日志分离，按日期自动切割、过期日志自动清理
数据库事务：增删改操作增加事务提交 / 回滚，保证数据一致性
五、项目目录结构
plaintext
ai_rag_chat/
├── routers/                  # 路由层：接口路由
│   ├── auth.py               # 注册、登录接口
│   └── chat.py               # 对话、会话、历史记录接口
├── services/                 # 服务层：核心业务逻辑
│   ├── auth_service.py       # 认证业务逻辑
│   ├── memory_service.py     # 聊天记录、会话管理逻辑
│   └── agent_service.py      # Agent 对话核心逻辑
├── tools/                    # 工具层：各类功能工具
│   ├── rag_tool.py           # RAG 知识库检索工具
│   ├── weather_tool.py       # 天气查询工具
│   └── text_splitter.py      # 文本切片工具
├── clients/                  # 客户端封装
│   └── llm_client.py         # 大模型客户端、工具定义、模型调用封装
├── utils/                    # 通用工具类
│   ├── logger.py             # 日志配置
│   ├── exception_handlers.py # 全局异常处理
│   ├── rate_limiter.py       # 接口限流器
│   └── background_tasks.py  # 后台日志统计任务
├── models.py                 # 数据库表模型定义
├── schemas.py                # Pydantic 数据校验模型
├── database.py               # 数据库连接、异步会话、生命周期管理
├── security.py               # 密码加密、JWT 签发与校验
├── config.py                 # 全局配置（读取 .env 环境变量）
├── seed_db.py                # 知识库离线数据灌入脚本
├── web_ui.py                 # Streamlit 前端交互页面
├── main.py                   # 项目入口、路由挂载、中间件、异常注册
├── .env                      # 环境变量配置文件（密钥、地址、参数）
├── requirements.txt          # 项目依赖清单
└── README.md                 # 项目说明文档
六、环境依赖与安装
1. 环境要求
Python 版本：3.10 ~ 3.12
数据库：PostgreSQL 14+，必须安装 PGVector 向量扩展
网络：可正常访问 硅基流动 / DeepSeek 大模型 API、天气第三方 API
2. 安装依赖
克隆项目到本地，进入项目根目录，执行依赖安装：
bash
运行
# 克隆仓库
git clone https://github.com/你的GitHub用户名/仓库名.git
cd 仓库名

# 安装依赖包
pip install -r requirements.txt
3. 配置环境变量
修改项目根目录下 .env 文件，必须补充所有密钥、地址、数据库配置，示例如下：
env
# 服务配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
ENVIRONMENT=development
LOG_LEVEL=INFO

# 大模型 API 配置
OPENAI_API_KEY=你的大模型密钥
OPENAI_BASE_URL=大模型接口地址
CHAT_MODEL=deepseek-ai/DeepSeek-V3
OPENAI_TEMPERATURE=0.1

# RAG & 向量配置
EMBEDDING_MODEL=BAAI/bge-m3
VECTOR_DIMENSION=1024
CHUNK_SIZE=350
CHUNK_OVERLAP=50
RECALL_TOP_K=10
RERANK_TOP_K=3
RERANK_SCORE_THRESHOLD=0.1

# 重排模型配置
RERANKER_API_URL=重排接口地址
RERANKER_API_KEY=重排服务密钥
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

# PostgreSQL 数据库配置
DB_HOST=你的数据库地址
DB_PORT=5432
DB_USER=数据库用户名
DB_PASSWORD=数据库密码
DB_NAME=数据库名
DATABASE_URL=postgresql+asyncpg://用户名:密码@地址:端口/数据库名

# JWT 安全配置
SECRET_KEY=自定义随机密钥
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
七、初始化数据库 & 灌入知识库
1. 数据库自动建表
项目基于 FastAPI lifespan 生命周期，启动后端服务时会自动执行数据表创建，无需手动执行 SQL。
2. 离线灌入企业知识库
在项目根目录创建 data 文件夹，新建 company_knowledge.txt，写入企业文档内容
执行数据灌入脚本，完成文本切片、向量化、入库：
bash
运行
python seed_db.py
脚本执行日志会输出切片数量、向量转换进度、入库结果。
八、项目启动方式
方式 1：启动后端服务（FastAPI 接口服务）
bash
运行
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
后端接口地址：http://localhost:8000
接口文档（自动生成）：http://localhost:8000/docs
方式 2：启动前端交互页面（Streamlit）
新开一个终端，保持后端服务运行状态，执行：
bash
运行
streamlit run web_ui.py
默认自动打开浏览器前端页面，可完成注册、登录、会话管理、对话交互全流程操作。
九、项目开发难点与优化方案（真实踩坑记录）
本项目开发过程中针对三大核心问题做针对性优化，所有优化逻辑均已落地到代码中：
问题 1：大模型绕过 RAG 工具，直接使用预训练知识回答，产生知识幻觉
现象：非寒暄类问题，大模型未调用知识库检索工具，回答内容与企业私有文档不符。
解决方案：
   (1)在系统 Prompt 中增加强约束规则，明确要求除日常寒暄外必须调用知识库工具；
   (2)增加代码级兜底机制：检测到大模型未触发工具调用时，程序强制调用 search_knowledge_base 工具，双重规避幻觉。
问题 2：知识库存在相关内容，但重排后检索结果显示为空
现象：数据库已存入对应文档，正常提问检索不到内容，关键词微调后可正常检索。
根因：重排序分数阈值设置过严，有效文本被过滤。
解决方案：
   (1)下调重排分数阈值，放宽匹配标准；
   (2)新增弹性兜底：若所有结果分数均低于阈值，强制选取分数最高的文本直接交由大模型解析，保证检索可用性。
问题 3：单段超长文本导致切片代码报错
现象：待处理文档中单段文本超过预设切块长度，原有切片逻辑无法处理，触发程序异常。
解决方案：
新增文本长度前置判断逻辑；超长段落单独按切块最大文本数固定长度强制切片，保留字符重叠区域，既修复报错，又避免上下文信息断裂。
十、项目说明 & 补充声明
项目定位：本项目为个人学习练手项目，用于学习 FastAPI、RAG、Agent、大模型应用开发全流程，仅做本地运行测试，未部署至线上生产环境。
代码辅助说明：项目开发过程中借助 AI 工具辅助代码编写、语法参考，所有逻辑调试、Bug 修复、功能优化均由本人独立完成。
扩展性：当前已实现基础能力，可后续扩展：文件上传解析、多模态问答、权限细分、对话导出等功能。
免责：本项目仅供技术学习交流，禁止用于商业用途。
十一、许可证
MIT License


