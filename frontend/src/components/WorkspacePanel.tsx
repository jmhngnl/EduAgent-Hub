import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createWorkspace,
  listWorkspaceMembers,
  listWorkspaces,
  removeWorkspaceMember,
  upsertWorkspaceMember,
} from "../auth/api";
import { useAuthStore } from "../auth/useAuthStore";

export function WorkspacePanel() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const activeWorkspaceId = useAuthStore((state) => state.activeWorkspaceId);
  const setActiveWorkspaceId = useAuthStore((state) => state.setActiveWorkspaceId);
  const setMe = useAuthStore((state) => state.setMe);
  const currentWorkspaces = useAuthStore((state) => state.workspaces);
  const [workspaceName, setWorkspaceName] = useState("");
  const [memberUsername, setMemberUsername] = useState("");
  const [memberRole, setMemberRole] = useState<"ADMIN" | "MEMBER" | "VIEWER">("MEMBER");

  const workspaceQuery = useQuery({ queryKey: ["workspaces"], queryFn: listWorkspaces });
  const workspaces = workspaceQuery.data ?? currentWorkspaces;
  const active = useMemo(() => workspaces.find((item) => item.id === activeWorkspaceId) ?? null, [workspaces, activeWorkspaceId]);
  const canManage = active?.role === "OWNER" || active?.role === "ADMIN";

  useEffect(() => {
    if (workspaceQuery.data && user) {
      setMe({ user, workspaces: workspaceQuery.data });
      if (!activeWorkspaceId && workspaceQuery.data[0]) setActiveWorkspaceId(workspaceQuery.data[0].id);
    }
  }, [workspaceQuery.data, user, activeWorkspaceId, setActiveWorkspaceId, setMe]);

  const membersQuery = useQuery({
    queryKey: ["workspace-members", activeWorkspaceId],
    queryFn: () => listWorkspaceMembers(activeWorkspaceId as string),
    enabled: Boolean(activeWorkspaceId && canManage),
  });

  const createMutation = useMutation({
    mutationFn: () => createWorkspace(workspaceName.trim()),
    onSuccess: async (workspace) => {
      setWorkspaceName("");
      setActiveWorkspaceId(workspace.id);
      await queryClient.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });

  const memberMutation = useMutation({
    mutationFn: () => upsertWorkspaceMember(activeWorkspaceId as string, memberUsername.trim(), memberRole),
    onSuccess: async () => {
      setMemberUsername("");
      await queryClient.invalidateQueries({ queryKey: ["workspace-members", activeWorkspaceId] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeWorkspaceMember(activeWorkspaceId as string, userId),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["workspace-members", activeWorkspaceId] }),
  });

  return (
    <main className="workspace-panel-v22">
      <header><span className="eyebrow">IDENTITY & ACCESS · V2.2</span><h1>Workspace 与成员权限</h1><p>身份由 Spring Security + JWT 验证；Workspace Membership / RBAC 由 Java Platform 作为唯一业务权限边界。</p></header>
      <div className="workspace-v22-grid">
        <section className="workspace-v22-card">
          <h2>我的 Workspaces</h2>
          <div className="workspace-v22-list">
            {workspaces.map((workspace) => (
              <button key={workspace.id} className={workspace.id === activeWorkspaceId ? "active" : ""} onClick={() => setActiveWorkspaceId(workspace.id)}>
                <span><strong>{workspace.name}</strong><code>{workspace.id}</code></span><em>{workspace.role}</em>
              </button>
            ))}
            {workspaces.length === 0 && <p>当前账号尚未加入 Workspace。可以创建一个新的 Workspace。</p>}
          </div>
          <div className="workspace-create-row"><input value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} placeholder="新 Workspace 名称" /><button disabled={!workspaceName.trim() || createMutation.isPending} onClick={() => createMutation.mutate()}>创建</button></div>
          {createMutation.isError && <div className="inline-error">{createMutation.error.message}</div>}
        </section>

        <section className="workspace-v22-card">
          <h2>成员与角色</h2>
          {!active && <p>请选择一个 Workspace。</p>}
          {active && !canManage && <p>当前角色为 <strong>{active.role}</strong>。成员管理需要 ADMIN 或 OWNER。</p>}
          {active && canManage && (
            <>
              <div className="member-add-row"><input value={memberUsername} onChange={(e) => setMemberUsername(e.target.value)} placeholder="已注册用户名" /><select value={memberRole} onChange={(e) => setMemberRole(e.target.value as typeof memberRole)}><option value="MEMBER">MEMBER</option><option value="VIEWER">VIEWER</option>{active.role === "OWNER" && <option value="ADMIN">ADMIN</option>}</select><button disabled={!memberUsername.trim() || memberMutation.isPending} onClick={() => memberMutation.mutate()}>添加 / 更新</button></div>
              {memberMutation.isError && <div className="inline-error">{memberMutation.error.message}</div>}
              <div className="member-list-v22">
                {(membersQuery.data ?? []).map((member) => (
                  <div key={member.userId}><span><strong>{member.displayName}</strong><small>@{member.username}</small></span><code>{member.role}</code>{member.role !== "OWNER" && <button onClick={() => { if (window.confirm(`移除 ${member.username}？`)) removeMutation.mutate(member.userId); }}>移除</button>}</div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
