import { useShallow } from "zustand/react/shallow";
import { useUiStore } from "../store/useUiStore";

const TOOL_LABELS: Record<string, string> = {
  search_knowledge: "知识库检索",
  search_academic_papers: "学术论文检索",
  read_paper_evidence: "论文证据读取",
  safe_calculator: "安全计算器",
};

export function TracePanel() {
  const trace = useUiStore(useShallow((state) => ({
    taskRoute: state.taskRoute,
    taskRouteLabel: state.taskRouteLabel,
    skill: state.skill,
    tools: state.tools,
    citations: state.citations,
    latencyMs: state.latencyMs,
    error: state.error,
    streaming: state.streaming,
  })));

  return (
    <aside className="trace-panel">
      <div className="trace-head">
        <div>
          <span className="eyebrow">AGENT TRACE</span>
          <h2>执行上下文</h2>
        </div>
        <span className={`run-state ${trace.streaming ? "running" : ""}`}>
          {trace.streaming ? "运行中" : "就绪"}
        </span>
      </div>

      <section className="trace-card">
        <div className="trace-card-title">Route</div>
        <div className="route-value">{trace.taskRouteLabel ?? "尚未路由"}</div>
        <code>{trace.taskRoute ?? "—"}</code>
      </section>

      <section className="trace-card">
        <div className="trace-card-title">Skill</div>
        <div className="skill-value">{trace.skill ?? "none"}</div>
      </section>

      <section className="trace-card tools-card">
        <div className="trace-card-title">Tools</div>
        {trace.tools.length === 0 ? (
          <p className="trace-empty">当前没有工具调用</p>
        ) : (
          <div className="tool-list">
            {trace.tools.map((tool, index) => (
              <div className="tool-row" key={`${tool.name}-${index}`}>
                <span className={`tool-status ${tool.status}`} />
                <div>
                  <strong>{TOOL_LABELS[tool.name] ?? tool.name}</strong>
                  <code>{tool.name}</code>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="trace-card source-card">
        <div className="trace-card-title">
          Sources <span>{trace.citations.length}</span>
        </div>
        {trace.citations.length === 0 ? (
          <p className="trace-empty">有真实引用时会显示在这里</p>
        ) : (
          <div className="source-list">
            {trace.citations.map((source, index) => {
              const body = (
                <>
                  <span className="source-index">{index + 1}</span>
                  <div>
                    <strong>{source.title || source.source}</strong>
                    <small>
                      {source.citation_type === "paper" ? "Paper" : "Knowledge"}
                      {source.year ? ` · ${source.year}` : ""}
                    </small>
                  </div>
                </>
              );
              return source.url ? (
                <a
                  className="source-row"
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  key={`${source.document_id}-${index}`}
                >
                  {body}
                </a>
              ) : (
                <div className="source-row" key={`${source.document_id}-${index}`}>
                  {body}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {trace.latencyMs !== null && (
        <div className="latency-row">
          <span>Agent latency</span>
          <strong>{(trace.latencyMs / 1000).toFixed(2)}s</strong>
        </div>
      )}
      {trace.error && <div className="trace-error">{trace.error}</div>}
    </aside>
  );
}
