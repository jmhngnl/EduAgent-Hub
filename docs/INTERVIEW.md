# 面试讲解与高频追问

## 30 秒项目介绍

EduAgent Hub 是一个教育场景的知识库与工作流智能体平台。用户上传学校制度、课程资料或实验室文档后，系统通过 Celery 异步完成 PDF 解析、文本切块、Embedding 和 pgvector 入库。问答阶段由 LangGraph 编排多轮 Agent，模型可以调用知识检索和安全计算工具，结果通过 SSE 返回，并带有文档来源。系统还提供 Redis 会话记忆、MCP 工具服务、Prometheus 指标、离线评估和 Docker Compose。

## 为什么选择 LangGraph

传统 Chain 更适合固定的线性流程，而 Agent 需要：

- 根据状态决定是否调用工具；
- 支持多次工具调用；
- 保留中间状态；
- 对循环次数做上限；
- 流式观察模型和工具事件；
- 后续接入人工审批和持久化检查点。

LangGraph 的价值是可控编排，不是让模型“更聪明”。

## RAG 完整链路

1. Loader：PDF/TXT/Markdown。
2. Splitter：递归切块，保留 overlap。
3. Embedding：将块转换成向量。
4. Storage：PostgreSQL + pgvector。
5. Retrieval：向量召回与全文召回。
6. Fusion：RRF 合并排名。
7. Generation：把 Top-K 上下文加入系统提示词。
8. Citation：返回来源、文档和 chunk。
9. Evaluation：Hit@K、引用率、答案召回和延迟。

## 为什么不只用向量检索

向量检索适合语义相似，但对课程编号、政策条款、专有名词和精确数字可能不稳定。全文检索能补充精确匹配。RRF 不要求两路分数在同一尺度上，因此比直接对分数加权更稳健。

## 为什么文档入库使用 Celery

PDF 解析和 Embedding 都是慢操作。同步执行会占用 Web Worker，导致接口超时。Celery 将任务放到 Redis Broker，由独立 Worker 处理，并支持重试、任务状态和水平扩展。

## 会话记忆如何实现

Redis 以 `session_id` 保存最近若干条用户和助手消息，设置 TTL。该记忆用于多轮上下文，不等于知识库。知识库是长期、可检索的外部事实；会话记忆是当前用户对话状态。

## Tool Calling、Agent、Workflow、MCP 的区别

- Tool Calling：模型生成结构化函数调用参数。
- Agent：模型结合状态反复判断和调用工具。
- Workflow：执行路径主要由程序预先定义。
- MCP：工具、资源和 Prompt 的标准化连接协议，不负责替代 Agent 编排。

## 如何防止跨租户数据泄漏

- API Key 可通过 `API_KEY_WORKSPACES` 映射到固定 workspace，请求切换租户时返回 403。
- 所有检索 SQL 必须带 `workspace_id` 条件；Agent 检索工具通过闭包捕获当前 workspace。
- 工具闭包捕获当前 workspace。
- 数据表建立 workspace/document 索引。
- 评估集中加入跨租户攻击用例。

当前开发模式允许不配置 API Key；正式部署必须启用 Key/JWT 映射，并建议增加 PostgreSQL Row-Level Security。

## 如何处理提示注入

当前实现包含基础规则检测、系统边界、工具白名单和拒绝透露系统信息。更完整方案应增加：

- 文档内容与用户指令分隔；
- 高风险工具人工确认；
- 工具参数 Schema 校验；
- 外部内容可信度标记；
- 输出敏感信息扫描；
- 攻击样本回归集。

## 为什么 Mock 模式仍然有价值

Mock 模式可以在没有模型 Key 时验证 API、文档切块、数据库、检索、租户隔离、前端、测试和 CI。它不能代表真实 LLM 效果，所以不能用于声称模型质量达标。

## 可能被问到的改进点

1. 使用 Cross-Encoder 或 LLM reranker。
2. 引入 PostgreSQL RLS。
3. LangGraph Postgres Checkpointer。
4. 大文件分片上传与对象存储。
5. OCR、表格和版面解析。
6. 写操作的 Human-in-the-loop。
7. LangSmith 或 OpenTelemetry 全链路 trace。
8. 基于真实数据集做 Prompt/RAG 消融。
