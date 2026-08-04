# 从 Demo 到可投递项目的推进路线

## Phase 1：代码跑通

- Docker Compose 启动 PostgreSQL、Redis、API、Worker 和前端。
- 上传 10 篇公开学校制度或课程文档。
- 完成文本入库、文件入库、搜索、对话和 MCP 演示。
- 为关键接口补充测试。

## Phase 2：真实模型和数据

- 接入一个真实 Chat Model 与 Embedding Model。
- 冻结 30～50 条问答回归集。
- 记录 baseline：仅向量检索。
- 对比：向量 + 全文 + RRF。
- 统计引用率、命中率、P95 延迟和平均 Token。

## Phase 3：增强 Agent

- 增加课程计划生成工具。
- 增加只读教务查询模拟 API。
- 对写操作加入人工确认节点。
- 使用 LangGraph 持久化 Checkpointer。
- 增加工具失败重试和补偿策略。

## Phase 4：生产化

- JWT/OAuth2 和 RBAC。
- PostgreSQL Row-Level Security。
- MinIO/S3 文件存储。
- OpenTelemetry Collector + Grafana。
- 限流、熔断、审计日志。
- Kubernetes 或云平台部署。

## 简历投递前验收

- README 有架构图、启动命令和接口说明。
- GitHub Actions 全绿。
- 有 2～3 分钟演示视频。
- 有真实评估报告，而非只展示页面。
- 能解释每个技术选择的业务原因。
- 不声称不存在的线上用户量和性能数据。
