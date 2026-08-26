import { logout } from "../auth/api";
import { useAuthStore } from "../auth/useAuthStore";
import type { Conversation } from "../types";

export type WorkspaceView = "chat" | "documents" | "workspace";

type Props = {
  conversations: Conversation[];
  selectedId: string | null;
  loading: boolean;
  activeView: WorkspaceView;
  onViewChange: (view: WorkspaceView) => void;
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

export function Sidebar({
  conversations,
  selectedId,
  loading,
  activeView,
  onViewChange,
  onSelect,
  onNew,
  onDelete,
}: Props) {
  const user = useAuthStore((state) => state.user);
  const workspaces = useAuthStore((state) => state.workspaces);
  const activeWorkspaceId = useAuthStore((state) => state.activeWorkspaceId);
  const setActiveWorkspaceId = useAuthStore((state) => state.setActiveWorkspaceId);
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
          <span>Enterprise Agent Workspace</span>
        </div>
      </div>

      <nav className="workspace-nav" aria-label="Workspace modules">
        <button className={activeView === "chat" ? "active" : ""} onClick={() => onViewChange("chat")}>
          <span>◫</span><div><strong>Chat</strong><small>Agent conversations</small></div>
        </button>
        <button className={activeView === "documents" ? "active" : ""} onClick={() => onViewChange("documents")}>
          <span>▤</span><div><strong>Documents</strong><small>Knowledge & papers</small></div>
        </button>
        <button className={activeView === "workspace" ? "active" : ""} onClick={() => onViewChange("workspace")}>
          <span>◇</span><div><strong>Workspace</strong><small>Members & RBAC</small></div>
        </button>
      </nav>

      {activeView === "chat" ? (
        <>
          <button className="new-chat" type="button" onClick={onNew}>
            <span>＋</span> 新建对话
          </button>
          <div className="conversation-scroll">
            {loading && <div className="sidebar-state">正在加载历史...</div>}
            {!loading && conversations.length === 0 && <div className="sidebar-state">暂无历史对话</div>}
            {[...sections.entries()].map(([label, items]) => (
              <section className="conversation-section" key={label}>
                <h3>{label}</h3>
                {items.map((item) => (
                  <div className={`conversation-item ${item.id === selectedId ? "active" : ""}`} key={item.id}>
                    <button type="button" className="conversation-select" onClick={() => onSelect(item.id)}>
                      <span className="conversation-title">{item.title || "New Chat"}</span>
                      <span className="conversation-time">{new Date(item.updatedAt).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</span>
                    </button>
                    <button className="conversation-delete" type="button" title="删除对话" aria-label={`删除 ${item.title}`} onClick={() => onDelete(item.id)}>×</button>
                  </div>
                ))}
              </section>
            ))}
          </div>
        </>
      ) : activeView === "documents" ? (
        <div className="module-copy">
          <span className="eyebrow">DOCUMENT CENTER</span>
          <strong>统一管理实验室知识与论文</strong>
          <p>V2.2 起写入权限由 Workspace RBAC 控制：VIEWER 只读，MEMBER 及以上可写。</p>
        </div>
      ) : (
        <div className="module-copy">
          <span className="eyebrow">IDENTITY & ACCESS</span>
          <strong>Workspace Membership</strong>
          <p>OWNER / ADMIN 管理成员；所有业务请求由 JWT 身份与 Workspace Membership 双重约束。</p>
        </div>
      )}

      <div className="workspace-chip">
        <div className="account-row-v22">
          <span><strong>{user?.displayName ?? "User"}</strong><small>@{user?.username ?? "unknown"}</small></span>
          <button type="button" onClick={() => void logout()}>退出</button>
        </div>
        <select className="account-workspace-select" value={activeWorkspaceId ?? ""} onChange={(e) => setActiveWorkspaceId(e.target.value || null)}>
          <option value="">选择 Workspace</option>
          {workspaces.map((workspace) => <option value={workspace.id} key={workspace.id}>{workspace.name} · {workspace.role}</option>)}
        </select>
        <div><span className="status-dot" /> Platform <code>V2.2</code></div>
      </div>
    </aside>
  );
}
