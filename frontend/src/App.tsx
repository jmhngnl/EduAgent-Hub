import { useEffect, useState } from "react";
import type { Conversation } from "./types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createConversation, deleteConversation, listConversations } from "./api/platform";
import { ChatPane } from "./components/ChatPane";
import { DocumentCenter } from "./components/DocumentCenter";
import { DocumentGuidePanel } from "./components/DocumentGuidePanel";
import { Sidebar, type WorkspaceView } from "./components/Sidebar";
import { TracePanel } from "./components/TracePanel";
import { useUiStore } from "./store/useUiStore";

const EMPTY_CONVERSATIONS: Conversation[] = [];

export function App() {
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState<WorkspaceView>("chat");
  const selectedId = useUiStore((state) => state.selectedConversationId);
  const setSelectedId = useUiStore((state) => state.setSelectedConversationId);
  const resetTrace = useUiStore((state) => state.resetTrace);

  const conversationsQuery = useQuery({
    queryKey: ["conversations", "demo"],
    queryFn: () => listConversations("demo"),
  });
  const conversations = conversationsQuery.data ?? EMPTY_CONVERSATIONS;

  useEffect(() => {
    if (conversationsQuery.isLoading) return;
    if (selectedId && conversations.some((item) => item.id === selectedId)) return;
    setSelectedId(conversations[0]?.id ?? null);
  }, [conversationsQuery.isLoading, conversations, selectedId, setSelectedId]);

  const createMutation = useMutation({ mutationFn: () => createConversation("demo") });
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
      ["conversations", "demo"],
      [conversation, ...conversations.filter((item) => item.id !== conversation.id)],
    );
    return conversation.id;
  }

  const selectedConversation = conversations.find((item) => item.id === selectedId) ?? null;

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        selectedId={selectedId}
        loading={conversationsQuery.isLoading}
        activeView={activeView}
        onViewChange={setActiveView}
        onSelect={(id) => {
          setActiveView("chat");
          setSelectedId(id);
          resetTrace();
        }}
        onNew={() => {
          setActiveView("chat");
          void createAndSelect();
        }}
        onDelete={(id) => {
          if (window.confirm("删除这个对话？历史记录将从列表中隐藏。")) deleteMutation.mutate(id);
        }}
      />

      {activeView === "chat" ? (
        <>
          <ChatPane conversationId={selectedId} title={selectedConversation?.title ?? null} createConversation={createAndSelect} />
          <TracePanel />
        </>
      ) : (
        <>
          <DocumentCenter />
          <DocumentGuidePanel />
        </>
      )}
    </div>
  );
}
