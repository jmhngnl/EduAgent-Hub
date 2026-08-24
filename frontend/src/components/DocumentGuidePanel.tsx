export function DocumentGuidePanel() {
  return (
    <aside className="trace-panel document-guide-panel">
      <div className="trace-head">
        <div><span className="eyebrow">DOCUMENT FLOW</span><h2>V2.1 数据链路</h2></div>
        <span className="run-state">BFF</span>
      </div>
      <section className="trace-card">
        <div className="trace-card-title">Write path</div>
        <div className="document-flow">
          <strong>React</strong><span>↓</span><strong>Spring Boot</strong><span>↓</span><strong>FastAPI</strong><span>↓</span><strong>Celery</strong><span>↓</span><strong>pgvector</strong>
        </div>
      </section>
      <section className="trace-card">
        <div className="trace-card-title">V2.1 Scope</div>
        <p className="guide-copy">当前版本恢复人工文件上传、文本入库、任务状态、文档列表与检索验证。浏览器不直接访问 Python Runtime。</p>
      </section>
      <section className="trace-card">
        <div className="trace-card-title">Deferred</div>
        <ul className="guide-list">
          <li>Agent 主动写知识库</li>
          <li>User / JWT / RBAC</li>
          <li>MinIO / RabbitMQ</li>
          <li>Document 完整生命周期</li>
        </ul>
      </section>
      <section className="trace-card">
        <div className="trace-card-title">Next</div>
        <p className="guide-copy">V2.2 在 Java Platform 引入 User、Workspace Membership、Spring Security、JWT 与 RBAC；V2.3 再升级正式 Document Platform。</p>
      </section>
    </aside>
  );
}
