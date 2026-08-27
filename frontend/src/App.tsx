import { useEffect, useState } from "react";
import type { Conversation } from "./types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { me, refreshSession } from "./auth/api";
import { useAuthStore } from "./auth/useAuthStore";
import { createConversation, deleteConversation, listConversations } from "./api/platform";
import { ChatPane } from "./components/ChatPane";
import { DocumentCenter } from "./components/DocumentCenter";
import { DocumentGuidePanel } from "./components/DocumentGuidePanel";
import { LoginPage } from "./components/LoginPage";
import { Sidebar, type WorkspaceView } from "./components/Sidebar";
import { TracePanel } from "./components/TracePanel";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { useUiStore } from "./store/useUiStore";
import "./v2.2.css";

const EMPTY_CONVERSATIONS: Conversation[] = [];

export function App() {
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState<WorkspaceView>("chat");
  const user = useAuthStore((state) => state.user);
  const accessToken = useAuthStore((state) => state.accessToken);
  const activeWorkspaceId = useAuthStore((state) => state.activeWorkspaceId);
  const bootstrapped = useAuthStore((state) => state.bootstrapped);
  const setSession = useAuthStore((state) => state.setSession);
  const setMe = useAuthStore((state) => state.setMe);
  const clearSession = useAuthStore((state) => state.clearSession);
  const setBootstrapped = useAuthStore((state) => state.setBootstrapped);
  const selectedId = useUiStore((state) => state.selectedConversationId);
  const setSelectedId = useUiStore((state) => state.setSelectedConversationId);
  const resetTrace = useUiStore((state) => state.resetTrace);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        if (accessToken) {
          try {
            const snapshot = await me(accessToken);
            if (!cancelled) setMe(snapshot);
          } catch {
            const session = await refreshSession();
            if (!cancelled) setSession(session);
          }
        } else {
          const session = await refreshSession();
          if (!cancelled) setSession(session);
        }
      } catch {
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setBootstrapped(true);
      }
    }
    void bootstrap();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setSelectedId(null);
    resetTrace();
    void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
  }, [activeWorkspaceId, queryClient, resetTrace, setSelectedId]);

  const conversationsQuery = useQuery({
    queryKey: ["conversations", activeWorkspaceId],
    queryFn: () => listConversations(activeWorkspaceId as string),
    enabled: Boolean(user && activeWorkspaceId),
  });
  const conversations = conversationsQuery.data ?? EMPTY_CONVERSATIONS;

  useEffect(() => {
    if (conversationsQuery.isLoading || !activeWorkspaceId) return;
    if (selectedId && conversations.some((item) => item.id === selectedId)) return;
    setSelectedId(conversations[0]?.id ?? null);
  }, [conversationsQuery.isLoading, conversations, selectedId, setSelectedId, activeWorkspaceId]);

  const createMutation = useMutation({
    mutationFn: () => {
      if (!activeWorkspaceId) throw new Error("请先选择 Workspace");
      return createConversation(activeWorkspaceId);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: async (_, deletedId) => {
      if (selectedId === deletedId) {
        setSelectedId(null);
        resetTrace();
      }
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  async function createAndSelect(): Promise<string> {
    const conversation = await createMutation.mutateAsync();
    setSelectedId(conversation.id);
    resetTrace();
    queryClient.setQueryData(
      ["conversations", activeWorkspaceId],
      [conversation, ...conversations.filter((item) => item.id !== conversation.id)],
    );
    return conversation.id;
  }

  if (!bootstrapped) {
    return <main className="auth-screen"><div className="auth-note">正在恢复 EduAgent 身份会话...</div></main>;
  }
  if (!user) return <LoginPage />;

  const selectedConversation = conversations.find((item) => item.id === selectedId) ?? null;
  const effectiveView = activeWorkspaceId ? activeView : "workspace";

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        selectedId={selectedId}
        loading={conversationsQuery.isLoading}
        activeView={effectiveView}
        onViewChange={setActiveView}
        onSelect={(id) => {
          setActiveView("chat");
          setSelectedId(id);
          resetTrace();
        }}
        onNew={() => {
          if (!activeWorkspaceId) {
            setActiveView("workspace");
            return;
          }
          setActiveView("chat");
          void createAndSelect();
        }}
        onDelete={(id) => {
          if (window.confirm("删除这个对话？历史记录将从列表中隐藏。")) deleteMutation.mutate(id);
        }}
      />

      {effectiveView === "chat" ? (
        <>
          <ChatPane conversationId={selectedId} title={selectedConversation?.title ?? null} createConversation={createAndSelect} />
          <TracePanel />
        </>
      ) : effectiveView === "documents" ? (
        <>
          <DocumentCenter />
          <DocumentGuidePanel />
        </>
      ) : (
        <>
          <WorkspacePanel />
          <aside className="trace-panel document-guide-panel">
            <div className="trace-head"><div><span className="eyebrow">SECURITY BOUNDARY</span><h2>V2.2 Access Model</h2></div><span className="run-state">JWT</span></div>
            <section className="trace-card"><div className="trace-card-title">Authority</div><p className="guide-copy">Spring Boot 是 User / Workspace / Membership / RBAC 的唯一业务权限源。Python Runtime 不接受浏览器 JWT。</p></section>
            <section className="trace-card"><div className="trace-card-title">Roles</div><p className="guide-copy">OWNER → ADMIN → MEMBER → VIEWER。文档写入至少需要 MEMBER；Chat/RAG 至少需要 VIEWER。</p></section>
          </aside>
        </>
      )}
    </div>
  );
}
