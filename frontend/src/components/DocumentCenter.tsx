import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getDocumentTask,
  ingestTextDocument,
  listDocuments,
  searchKnowledge,
  uploadDocument,
} from "../api/platform";
import type { DocumentType, IngestResponse, KnowledgeSearchResponse } from "../types";

const WORKSPACE_ID = "demo";

type Filter = DocumentType | "all";

function taskStateLabel(state?: string): string {
  switch (state) {
    case "PENDING": return "排队中";
    case "STARTED": return "解析与索引中";
    case "SUCCESS": return "已完成";
    case "FAILURE": return "失败";
    default: return state || "等待任务";
  }
}

export function DocumentCenter() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");
  const [file, setFile] = useState<File | null>(null);
  const [fileType, setFileType] = useState<DocumentType>("paper");
  const [fileDocumentId, setFileDocumentId] = useState("");
  const [textType, setTextType] = useState<DocumentType>("lab_document");
  const [textDocumentId, setTextDocumentId] = useState("");
  const [textSource, setTextSource] = useState("实验室规则.md");
  const [textValue, setTextValue] = useState("");
  const [lastIngest, setLastIngest] = useState<IngestResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<KnowledgeSearchResponse | null>(null);

  const documentsQuery = useQuery({
    queryKey: ["documents", WORKSPACE_ID, filter],
    queryFn: () => listDocuments(WORKSPACE_ID, filter),
  });

  const taskQuery = useQuery({
    queryKey: ["document-task", lastIngest?.task_id],
    queryFn: () => getDocumentTask(lastIngest?.task_id as string),
    enabled: Boolean(lastIngest?.task_id),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state === "SUCCESS" || state === "FAILURE" ? false : 1500;
    },
  });

  useEffect(() => {
    if (taskQuery.data?.state === "SUCCESS") {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    }
  }, [taskQuery.data?.state, queryClient]);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("请选择 PDF、TXT 或 Markdown 文件");
      return uploadDocument({
        file,
        workspaceId: WORKSPACE_ID,
        documentId: fileDocumentId,
        documentType: fileType,
      });
    },
    onSuccess: (result) => {
      setLastIngest(result);
      setFile(null);
      setFileDocumentId("");
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const textMutation = useMutation({
    mutationFn: () => {
      if (!textDocumentId.trim()) throw new Error("请填写文档 ID");
      if (!textSource.trim()) throw new Error("请填写来源名称");
      if (!textValue.trim()) throw new Error("请输入需要写入知识库的文本");
      return ingestTextDocument({
        workspaceId: WORKSPACE_ID,
        documentId: textDocumentId.trim(),
        source: textSource.trim(),
        text: textValue.trim(),
        documentType: textType,
      });
    },
    onSuccess: (result) => {
      setLastIngest(result);
      setTextValue("");
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const searchMutation = useMutation({
    mutationFn: () => searchKnowledge({
      workspaceId: WORKSPACE_ID,
      query: searchQuery.trim(),
      documentType: filter,
      topK: 6,
    }),
    onSuccess: setSearchResult,
  });

  const documents = documentsQuery.data?.documents ?? [];
  const totalChunks = useMemo(
    () => documents.reduce((sum, item) => sum + item.chunk_count, 0),
    [documents],
  );
  const taskState = taskQuery.data?.state ?? (lastIngest?.status === "indexed" ? "SUCCESS" : undefined);

  return (
    <main className="document-center">
      <header className="document-header">
        <div>
          <span className="eyebrow">DOCUMENT CENTER · V2.1</span>
          <h1>知识库与论文资料</h1>
          <p>由 Java Platform 接收用户操作，再调用 FastAPI / Celery 完成解析、切分与 pgvector 索引。</p>
        </div>
        <div className="document-summary">
          <strong>{documents.length}</strong>
          <span>documents</span>
          <strong>{totalChunks}</strong>
          <span>chunks</span>
        </div>
      </header>

      <div className="document-scroll">
        <section className="document-actions-grid">
          <article className="document-card">
            <div className="document-card-head">
              <div><span className="eyebrow">FILE INGESTION</span><h2>上传资料</h2></div>
              <span className="document-badge">PDF / TXT / MD</span>
            </div>
            <label className="field-label">资料类型
              <select value={fileType} onChange={(e) => setFileType(e.target.value as DocumentType)}>
                <option value="paper">学术论文</option>
                <option value="lab_document">实验室资料 / 规则</option>
              </select>
            </label>
            <label className="field-label">Document ID（可选）
              <input value={fileDocumentId} onChange={(e) => setFileDocumentId(e.target.value)} placeholder="留空自动生成 UUID" />
            </label>
            <label className="drop-zone">
              <input
                type="file"
                accept=".pdf,.txt,.md,.markdown"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <strong>{file?.name ?? "选择 PDF、TXT 或 Markdown"}</strong>
              <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "最大 30 MB · 上传后异步索引"}</span>
            </label>
            <button className="primary-action" disabled={uploadMutation.isPending || !file} onClick={() => uploadMutation.mutate()}>
              {uploadMutation.isPending ? "正在上传..." : "上传并建立索引"}
            </button>
            {uploadMutation.isError && <div className="inline-error">{uploadMutation.error.message}</div>}
          </article>

          <article className="document-card">
            <div className="document-card-head">
              <div><span className="eyebrow">TEXT INGESTION</span><h2>粘贴规则或笔记</h2></div>
              <span className="document-badge">同步入库</span>
            </div>
            <div className="two-fields">
              <label className="field-label">资料类型
                <select value={textType} onChange={(e) => setTextType(e.target.value as DocumentType)}>
                  <option value="lab_document">实验室资料 / 规则</option>
                  <option value="paper">论文文本</option>
                </select>
              </label>
              <label className="field-label">Document ID
                <input value={textDocumentId} onChange={(e) => setTextDocumentId(e.target.value)} placeholder="gpu-policy-2026" />
              </label>
            </div>
            <label className="field-label">来源名称
              <input value={textSource} onChange={(e) => setTextSource(e.target.value)} placeholder="实验室 GPU 使用规范.md" />
            </label>
            <label className="field-label">正文
              <textarea rows={7} value={textValue} onChange={(e) => setTextValue(e.target.value)} placeholder="把需要被 RAG 检索的规则、说明或论文文本粘贴到这里..." />
            </label>
            <button className="primary-action" disabled={textMutation.isPending} onClick={() => textMutation.mutate()}>
              {textMutation.isPending ? "正在写入..." : "写入知识库"}
            </button>
            {textMutation.isError && <div className="inline-error">{textMutation.error.message}</div>}
          </article>
        </section>

        {lastIngest && (
          <section className="ingest-status-card">
            <div>
              <span className="eyebrow">LATEST INGESTION</span>
              <h3>{lastIngest.document_id}</h3>
              <p>{lastIngest.document_type === "paper" ? "学术论文" : "实验室资料"}</p>
            </div>
            <div className={`task-state state-${(taskState ?? "pending").toLowerCase()}`}>
              <span />
              <div>
                <strong>{taskStateLabel(taskState)}</strong>
                <small>{lastIngest.task_id ? `Task ${lastIngest.task_id}` : `${lastIngest.chunks_indexed} chunks indexed`}</small>
              </div>
            </div>
          </section>
        )}

        <section className="library-section">
          <div className="library-toolbar">
            <div><span className="eyebrow">INDEXED LIBRARY</span><h2>已入库资料</h2></div>
            <div className="filter-tabs">
              {(["all", "lab_document", "paper"] as Filter[]).map((value) => (
                <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>
                  {value === "all" ? "全部" : value === "paper" ? "论文" : "实验室资料"}
                </button>
              ))}
              <button onClick={() => void documentsQuery.refetch()}>刷新</button>
            </div>
          </div>
          {documentsQuery.isLoading ? <div className="document-empty">正在读取知识库...</div> : null}
          {documentsQuery.isError ? <div className="inline-error">{(documentsQuery.error as Error).message}</div> : null}
          {!documentsQuery.isLoading && documents.length === 0 ? <div className="document-empty">当前筛选下还没有已索引资料。</div> : null}
          <div className="document-table">
            {documents.map((doc) => (
              <article className="document-row" key={`${doc.document_type}-${doc.document_id}`}>
                <span className={`doc-type ${doc.document_type}`}>{doc.document_type === "paper" ? "PAPER" : "LAB"}</span>
                <div className="document-row-main">
                  <strong>{doc.source}</strong>
                  <code>{doc.document_id}</code>
                </div>
                <div className="chunk-count"><strong>{doc.chunk_count}</strong><span>chunks</span></div>
              </article>
            ))}
          </div>
        </section>

        <section className="library-section">
          <div className="library-toolbar">
            <div><span className="eyebrow">RETRIEVAL CHECK</span><h2>验证检索结果</h2></div>
          </div>
          <div className="knowledge-search-bar">
            <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="例如：GPU 申请需要哪些材料？" onKeyDown={(e) => { if (e.key === "Enter" && searchQuery.trim()) searchMutation.mutate(); }} />
            <button disabled={!searchQuery.trim() || searchMutation.isPending} onClick={() => searchMutation.mutate()}>
              {searchMutation.isPending ? "检索中" : "检索"}
            </button>
          </div>
          {searchMutation.isError && <div className="inline-error">{searchMutation.error.message}</div>}
          {searchResult && (
            <div className="search-results">
              {searchResult.results.length === 0 && <div className="document-empty">没有命中内容。</div>}
              {searchResult.results.map((item, index) => (
                <article className="search-result" key={item.id}>
                  <div><span>#{index + 1}</span><strong>{item.source}</strong><code>{item.score.toFixed(4)}</code></div>
                  <p>{item.content}</p>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
