# 更新日志

所有项目的显著变更都将记录在此文件中。


## [v3.4] - 文档补全
### 功能优化
- README 补充「重建索引前必须准备 `app/graphrag/data/.env`」：三份 `settings*.yaml` 的模型配置
  全部使用 `${VAR}` 占位符，GraphRAG 加载时读取同目录 `data/.env` 做替换；该文件被
  `app/graphrag/.gitignore` 排除，git 拉取后不存在，缺失时 `load_config` 直接抛 `KeyError`。
  此前 README 只字未提，属于「上传文档建索引」的隐性前置条件
- README 补充「测试」章节：说明 `python tests/test_contract.py` / `pytest` 跑什么、何时应重跑，
  并区分自动化契约测试与 `app/test/` 下的手工调试脚本
- README 必填项之外补充「按需填写」的配置组说明（词向量 `EMBEDDING_*`、GraphRAG 查询 `GRAPHRAG_*`）
- 环境要求表修正 Node.js 版本：vite 6 要求 18 / 20 / 22+，**不支持 19、21**，原文的「18+」过宽
- 目录结构补 `pytest.ini` 与 `graphrag/data/.env` 两项

### 问题修复
- 新增缺失的 `LICENSE` 文件（MIT，并注明内嵌 Microsoft GraphRAG、Neo4j agentic-rag 示例等
  第三方组件沿用其自身许可证），消除「README 声称 MIT 却无许可证文件」的不一致

### 文档核对结论
逐条对照代码复核了 README：目录结构与实际文件一致、18 条接口路由与文档表一致
（`/health`、`/chat-rag` 确由 `main.py` 顶层挂载、不带 `/api` 前缀）、图谱模型
8 类节点 / 9 类关系及方向与 `create_neo4j_import.py` 一致、`run.py` 环境变量与默认值一致、
`init_db.py` / `preflight.py` 参数说明一致。


## [v3.3] - 跨机可移植性修复
### 安全问题
- `agentic_rag_agents/components/cypher_tools/node.py` 注释示例中残留真实 Neo4j 密码，
  已替换为占位符（v3.1 只扫描了 `.env.example`，漏掉了源码内嵌示例）
- 清除全项目对原作者内网地址 `192.168.110.131` 的引用：`llm_backend/.env` 的
  `OLLAMA_BASE_URL`、三份 `settings*.yaml` 的注释示例、`app/test/ollama_benchmark.py`

### 问题修复（换机后必然失败的问题）
- `data/settings_pdf.yaml` 的 `mineru_api_url` 原指向作者内网 `http://192.168.110.131:8000/`、
  `mineru_output_dir` 原为 Linux 路径 `/home/07_minerU/tmp/`。这两项由
  `app/services/indexing_service.py` 在上传 PDF 时实时加载，**任何其他机器上 PDF 建索引都会失败**。
  现改为可移植默认值（`http://127.0.0.1:8081/` 与 `./data/mineru_output`），并支持
  `MINERU_API_URL` / `MINERU_OUTPUT_DIR` 环境变量覆盖，换环境无需改仓库内配置文件
- `app/graphrag/dev/` 下 4 个脚本共 6 处硬编码 `C:\Users\Lenovo\Desktop\...` 绝对路径，
  改为基于 `__file__` 相对推导，换机后可直接运行
- 三份 `data/settings*.yaml`、`app/graphrag/settings.yaml`、`test_data/settings.yaml` 中的
  `db_uri` 由 `output\lancedb` 改为 `output/lancedb`：反斜杠在 Linux 上会被当作文件名的一部分，
  导致向量库写到名为 `output\lancedb` 的目录
- `agentic_rag_agents/agent.py` 增加 `NEO4J_URL` → `NEO4J_URI` 命名桥接：项目 `.env` 用的是
  `NEO4J_URL`，而 `Neo4jGraph` 默认只认 `NEO4J_URI`，单独跑 LangGraph Studio 时会取到空 URI
- `indexing_service.py` 的 `process_file` 提前取出 `file_path`，避免异常分支引用未绑定变量
  抛 `NameError` 掩盖真实错误

### 清理
- 删除 23 个作者机器遗留日志（`*.log` / `logs.json` / `benchmark_*.json`）与
  `data/pdf_csv_exports/` 全部调试产物；另有 2 个日志因回收站不可用改为清空内容
- 保留 `data/output/`（现有索引，查询必需）与 `data/cache/`（LLM 响应缓存，重跑索引可省成本）

### 功能优化
- `scripts/preflight.py` 新增两项检查：
  - **H 可移植性**：扫描项目自有文件，检出机器相关绝对路径与路径类配置中的反斜杠写法
  - **I PDF 索引**：报告 MinerU 生效地址并探测连通性，不可达时说明只影响 PDF 这一条链路
- README 补充 MinerU 说明：区分「本地知识库 PDF（PyPDF2，无需外部服务）」与
  「GraphRAG PDF 索引（依赖 MinerU）」，并新增对应 FAQ


## [v3.2] - 可部署性加固
### 功能优化
- `run.py` 改为环境变量驱动，开发/生产共用一份代码：`APP_ENV`（`dev` 时自动开启热重载与访问日志，
  默认 `prod`）、`HOST`、`PORT`、`RELOAD`、`LOG_LEVEL`、`WORKERS`；并把 `os.chdir` 提前到
  导入 `app.*` 之前，避免以其他工作目录启动时 `.env`、`logs/`、`uploads/` 定位错乱
- `WORKERS` 默认固定为 1：LangGraph 的断点在 `MemorySaver` 里属进程内存态，多进程会让
  `/api/langgraph/resume` 失效；设为 >1 时打印告警说明
- 新增 `llm_backend/scripts/preflight.py` 部署前自检（零依赖可运行）：检查 Python 版本、
  31 个关键第三方包、`.env` 必填项与 `SECRET_KEY` 强度、前端构建产物自洽性、运行目录可写、
  GraphRAG 索引、MySQL/Redis/Neo4j 端口连通性、监听端口占用，按 PASS/WARN/FAIL 分级并给出退出码
- README 新增「部署」章节：部署最小条件、完整部署流程、Nginx 反代示例（含 SSE 关闭
  `proxy_buffering` 的关键配置）、上线检查清单、常见部署失败原因

### 已知约束（已写入文档）
- **torch 是启动硬依赖**：`embedding_service.py` 在模块顶层导入 `sentence-transformers`，
  且 `main.py` 链式导入它，因此不使用本地知识库也必须装齐，部署需要 ≥5GB 磁盘
- 部署无需 Node.js 环境，前端构建产物已随包提供并由后端同源托管

### 问题修复
- 修正 README 中索引产物路径描述（`output/lancedb` 实际位于 `app/graphrag/data/output/lancedb`）


## [v3.1] - 完整性修复
### 安全问题
- `.env.example` 中移除真实数据库密码，改为占位符；补充 `SECRET_KEY` / `ALGORITHM` /
  `ACCESS_TOKEN_EXPIRE_MINUTES` / `DEEPSEEK_REASON_MODEL` / 词向量相关配置项
- `llm_backend/.env` 生成随机 `SECRET_KEY`，不再回退到代码内置的默认值
  （默认值可被用于伪造任意用户的 JWT）

### 问题修复
- `scripts/init_db.py` 默认行为由「先 drop_all 再 create_all」改为「只创建缺失的表」，
  清空重建需显式 `--reset` 并二次确认；同时用退出码反映真实执行结果
- 补充 `app/lg_agent/kg_sub_graph/planner/__init__.py` 并导出 `create_planner_node`，
  修复 `multi_tools.py` 中 `from app.lg_agent.kg_sub_graph.planner import create_planner_node`
  必然 ImportError 的问题
- 为 `app/tools`、`app/prompts`、`app/schemas`、`app/test`、`kg_sub_graph` 及其
  `planner`、`ps_genai_agents` 等 10 个目录补齐 `__init__.py`，不再依赖隐式命名空间包
- `agentic_rag_agents/agent_cooking_assistant.py` 增加说明：该上游示例脚本在本项目中不可直接运行

### 功能优化
- `requirements.txt`：显式声明 `neo4j`、新增 `pytest`，注明 Python 版本约束（3.11 ~ 3.12，
  由 graphrag 的 `<3.13` 与 ipython 的 `>=3.11` 共同决定）与 3 个可选依赖的用途
- 新增 `tests/test_contract.py`：前后端接口契约、构建产物、凭据占位符、Python 包结构四项回归检查
- 重写 `README.md`：修正端口（9000 → 8000）、配置文件路径，删除与项目无关的
  「电商商品数据服务」章节（其引用的 `product_service.py` / `frontend_demo.py` 并不存在），
  改写为与实际代码一致的 GraphRAG 电商智能体说明


## [v3.0] - 【AssistGen】
### 基础知识
- DeepSeek Function Calling 工具调用


### 功能版本
- 用户历史会话记录管理
  - 会话删除
  - 会话名称修改


### 功能优化
- 问答/深度思考接口增加user_id、conversation_id参数
- 问答/深度思考接口增加回调机制
- 问答/深度思考接口增加redis上下文缓存管理

### 问题修复
- 解决 init_db.py脚本异步运行问题



## [v3.0] - 【AssistGen】
### 基础知识
- DeepSeek API 硬盘上下文缓存 
- Redis 内存数据库安装及启动方法
- 基于 Redis 的Prompt cache缓存管理
    - 完全匹配规则
    - 基于语义的向量匹配规则

### 功能版本
- 用户历史会话记录管理
  - Mysql 会话表、消息表结构设计与接入
  - 左侧会话记录列表展示


### 功能优化
- 问答/深度思考接口增加user_id、conversation_id参数
- 问答/深度思考接口增加回调机制
- 问答/深度思考接口增加redis上下文缓存管理

### 问题修复
- 解决 init_db.py脚本异步运行问题

## [v2.0] - 【AssistGen】Ch 2.1 ~ Ch 2.5
### 基础知识
- FastAPI基础知识
- Mysql 数据库接入
- Ollama 压力测试

### 功能版本
- Mysql 表结构设计与初始化脚本 - 用户表
- 实现用户注册、登入、登出
- 实现 DeepSeek v3 & Ollama + 问答类模型（如 qwen2.5）流式问答
- 实现 DeepSeek R1 & Ollama + Deepseek r1  深度思考流式问答 
- 实现 Deepseek v3  + Serper API 实时联网检索 Baseline
- 实现 Deepseek v3 + sentence-transformers 本地知识库问答 Baseline

### 功能优化
- 优化项目启动文件`run.py`

## [v1.0] - 【AssistGen】Ch 1.1 ~ Ch 1.6
### 基础知识
- Ollama 本地部署 DeepSeek R1 模型完整流程
- Ollama REST API 核心接口：api/generate & api/chat
- Ollama 兼容 OpenAI API 接口规范
- Deepseek v3 & R1 在线 API 调用方法