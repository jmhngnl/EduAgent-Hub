import type { Conversation } from "../types";

type Props = {
  conversations: Conversation[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
};

function sectionLabel(updatedAt: string): string {
  const date = new Date(updatedAt);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const value = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const diff = Math.round((today - value) / 86_400_000);
  if (diff <= 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff < 7) return "过去 7 天";
  return "更早";
}

export function Sidebar({ conversations, selectedId, loading, onSelect, onNew, onDelete }: Props) {
  const sections = new Map<string, Conversation[]>();
  for (const item of conversations) {
    const label = sectionLabel(item.updatedAt);
    sections.set(label, [...(sections.get(label) ?? []), item]);
  }

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-mark">E</div>
        <div>
          <strong>EduAgent Hub</strong>
          <span>AI Research Workspace</span>
        </div>
      </div>

      <button className="new-chat" type="button" onClick={onNew}>
        <span>＋</span> 新建对话
      </button>

      <div className="conversation-scroll">
        {loading && <div className="sidebar-state">正在加载历史...</div>}
        {!loading && conversations.length === 0 && (
          <div className="sidebar-state">暂无历史对话</div>
        )}
        {[...sections.entries()].map(([label, items]) => (
          <section className="conversation-section" key={label}>
            <h3>{label}</h3>
            {items.map((item) => (
              <div
                className={`conversation-item ${item.id === selectedId ? "active" : ""}`}
                key={item.id}
              >
                <button type="button" className="conversation-select" onClick={() => onSelect(item.id)}>
                  <span className="conversation-title">{item.title || "New Chat"}</span>
                  <span className="conversation-time">
                    {new Date(item.updatedAt).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </button>
                <button
                  className="conversation-delete"
                  type="button"
                  title="删除对话"
                  aria-label={`删除 ${item.title}`}
                  onClick={() => onDelete(item.id)}
                >
                  ×
                </button>
              </div>
            ))}
          </section>
        ))}
      </div>

      <div className="workspace-chip">
        <span className="status-dot" />
        Workspace: demo
      </div>
    </aside>
  );
}
