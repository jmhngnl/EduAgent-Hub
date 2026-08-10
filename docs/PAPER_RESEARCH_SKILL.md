# Paper Research Skill 使用说明

该功能把“Tool”和“Skill”分开：

- `search_academic_papers`：调用 Semantic Scholar Academic Graph，负责发现论文和获取元数据。
- `read_paper_evidence`：只在当前 workspace 的知识库中检索指定 `document_id`，负责从已上传 PDF 中收集背景、方法、实验、指标、消融和局限证据。
- `skills/paper-reader/SKILL.md`：规定论文推荐和论文解读的步骤、输出结构以及禁止幻觉的规则。

## 1. 推荐论文

直接在 Agent 对话中输入：

```text
推荐 2024-2026 年 CMR 跨模态生成方向的论文，重点关注 diffusion、flow matching 和 lesion preservation。
```

Agent 会根据需要调用 `search_academic_papers`。

Semantic Scholar API Key 可选：

```env
SEMANTIC_SCHOLAR_API_KEY=
PAPER_SEARCH_TIMEOUT_SECONDS=20
PAPER_SEARCH_MAX_RESULTS=8
SKILLS_DIR=skills
```

## 2. 深度解读论文

先使用现有文件上传接口把 PDF 放入知识库：

```bash
curl -X POST "http://127.0.0.1:8000/v1/knowledge/files" \
  -H "X-API-Key: demo" \
  -F "file=@/path/to/paper.pdf;type=application/pdf" \
  -F "workspace_id=demo" \
  -F "document_id=motfm-paper"
```

等待 Celery 任务完成后，在 Agent 中输入：

```text
请深度解读 document_id=motfm-paper 这篇论文，重点讲背景、创新、网络结构、数据集、指标、消融和局限。
```

Agent 会调用 `read_paper_evidence`，从该 document_id 的 PDF chunk 中按多个研究问题检索证据，再依据 Paper Reader Skill 输出结构化解读。

## 3. 推荐的测试问题

```text
推荐最近三年 cardiac MRI synthesis 论文，优先 flow matching。
```

```text
这几篇里面哪两篇最适合作为 CMR flow matching baseline？为什么？
```

```text
请解读 document_id=motfm-paper 的实验指标。所有数字都必须给出论文证据，不确定就说明没检索到。
```

## 4. 当前边界

- 论文搜索使用外部元数据，不等于读过论文全文。
- 深度实验解读要求 PDF 已经进入 EduAgent RAG。
- 当前 PDF 解析基于 `pypdf` 文本抽取；复杂表格、矢量图和公式可能丢失。若关键指标只存在于图表中，需要后续增加图表解析模块。
