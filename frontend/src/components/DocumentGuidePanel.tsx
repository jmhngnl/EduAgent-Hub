export function DocumentGuidePanel() {
  return (
    <aside className="trace-panel document-guide-panel">
      <div className="trace-head">
        <div><span className="eyebrow">DOCUMENT FLOW</span><h2>V2.2 安全数据链路</h2></div>
        <span className="run-state">RBAC</span>
      </div>
      <section className="trace-card">
        <div className="trace-card-title">Write path</div>
        <div className="document-flow">
          <strong>React + JWT</strong><span>↓</span><strong>Spring Security</strong><span>↓</span><strong>Workspace RBAC</strong><span>↓</span><strong>FastAPI Internal</strong><span>↓</span><strong>Celery / pgvector</strong>
        </div>
      </section>
      <section className="trace-card">
        <div className="trace-card-title">Authorization</div>
        <p className="guide-copy">VIEWER 可以查询与阅读；MEMBER / ADMIN / OWNER 可以上传或写入知识库。浏览器传入的 workspace 只有经过 Java Membership 校验后才会进入 Python Runtime。</p>
      </section>
      <section className="trace-card">
        <div className="trace-card-title">Deferred</div>
        <ul className="guide-list">
          <li>Agent 主动写知识库</li>
          <li>MinIO / RabbitMQ</li>
          <li>Document 完整生命周期</li>
          <li>Audit / Rate Limit</li>
        </ul>
      </section>
      <section className="trace-card">
        <div className="trace-card-title">Next</div>
        <p className="guide-copy">V2.3 升级 Document Platform；V2.4 再引入 HITL、Agent 写操作与 LangGraph durable execution。</p>
      </section>
    </aside>
  );
}
