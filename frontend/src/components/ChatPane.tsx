import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import { listMessages, streamMessage } from "../api/platform";
import { useUiStore } from "../store/useUiStore";
import type { ChatMessage, Citation } from "../types";

type Props = {
  conversationId: string | null;
  title: string | null;
  createConversation: () => Promise<string>;
};

function parseJsonArray<T>(raw: string | null): T[] {
  if (!raw) return [];
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? (value as T[]) : [];
  } catch {
    return [];
  }
}

const ROUTE_LABELS: Record<string, string> = {
  general: "通用任务",
  lab_resource: "实验室资源任务",
  paper_reading: "论文解读任务",
};

export function ChatPane({ conversationId, title, createConversation }: Props) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [optimisticUser, setOptimisticUser] = useState<string | null>(null);
  const [streamText, setStreamText] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const controllerRef = useRef<AbortController | null>(null);

  const resetTrace = useUiStore((state) => state.resetTrace);
  const setStreaming = useUiStore((state) => state.setStreaming);
  const setRoute = useUiStore((state) => state.setRoute);
  const toolStarted = useUiStore((state) => state.toolStarted);
  const toolFinished = useUiStore((state) => state.toolFinished);
  const streamDone = useUiStore((state) => state.streamDone);
  const streamError = useUiStore((state) => state.streamError);
  const restoreTrace = useUiStore((state) => state.restoreTrace);
  const streaming = useUiStore((state) => state.streaming);

  const messagesQuery = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () => listMessages(conversationId as string),
    enabled: Boolean(conversationId),
  });

  const messages = messagesQuery.data ?? [];
  const lastAssistant = useMemo(
    () => [...messages].reverse().find((item) => item.role === "ASSISTANT"),
    [messages],
  );

  useEffect(() => {
    stickToBottomRef.current = true;
    controllerRef.current?.abort();
    setOptimisticUser(null);
    setStreamText("");
    setLocalError(null);
    if (!lastAssistant) {
      resetTrace();
      return;
    }
    const tools = parseJsonArray<string>(lastAssistant.toolCallsJson).map((name) => ({
      name,
      status: "done" as const,
    }));
    restoreTrace({
      taskRoute: lastAssistant.taskRoute,
      taskRouteLabel: lastAssistant.taskRoute
        ? ROUTE_LABELS[lastAssistant.taskRoute] ?? lastAssistant.taskRoute
        : null,
      skill: lastAssistant.skillName,
      tools,
      citations: parseJsonArray<Citation>(lastAssistant.citationsJson),
      latencyMs: lastAssistant.latencyMs,
      streaming: false,
    });
  }, [conversationId, lastAssistant?.id]);

  useEffect(() => {
    const container = messageListRef.current;
    if (!container || !stickToBottomRef.current) return;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: streaming ? "auto" : "smooth",
    });
  }, [conversationId, messages.length, lastAssistant?.id, streamText, optimisticUser, streaming]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  async function send(): Promise<void> {
    const content = draft.trim();
    if (!content || streaming) return;

    stickToBottomRef.current = true;
    let id = conversationId;
    if (!id) id = await createConversation();

    setDraft("");
    setOptimisticUser(content);
    setStreamText("");
    setLocalError(null);
    resetTrace();
    setStreaming(true);

    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      await streamMessage(
        id,
        content,
        {
          onRoute: setRoute,
          onToken: (token) => setStreamText((current) => current + token),
          onToolStart: ({ name }) => toolStarted(name),
          onToolEnd: ({ name }) => toolFinished(name),
          onDone: streamDone,
          onError: (message) => {
            streamError(message);
            setLocalError(message);
          },
        },
        controller.signal,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["messages", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
      ]);
      setOptimisticUser(null);
      setStreamText("");
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        const message = error instanceof Error ? error.message : "请求失败";
        streamError(message);
        setLocalError(message);
        await queryClient.invalidateQueries({ queryKey: ["messages", id] });
        setOptimisticUser(null);
      }
    } finally {
      setStreaming(false);
      controllerRef.current = null;
    }
  }

  return (
    <main className="chat-pane">
      <header className="chat-header">
        <div>
          <span className="eyebrow">CONVERSATION</span>
          <h1>{title || "New research conversation"}</h1>
        </div>
        <div className="runtime-badge">
          <span /> Java Platform → LangGraph
        </div>
      </header>

      <div
        className="message-list"
        ref={messageListRef}
        onScroll={(event) => {
          const container = event.currentTarget;
          const distanceToBottom =
            container.scrollHeight - container.scrollTop - container.clientHeight;
          stickToBottomRef.current = distanceToBottom < 96;
        }}
      >
        {(!conversationId || (!messagesQuery.isLoading && messages.length === 0 && !optimisticUser)) && (
          <section className="welcome-card">
            <span className="welcome-kicker">EDUAGENT V2.1</span>
            <h2>把研究问题变成可追踪的 Agent 工作流</h2>
            <p>
              对话历史会写入 MySQL；实时回答由 Spring Boot 代理 LangGraph SSE，右侧同步展示 Route、Skill、Tools 与真实 Sources。
            </p>
            <div className="suggestion-grid">
              <button type="button" onClick={() => setDraft("Flow Matching 和 Diffusion 有什么区别？")}>
                比较 Flow Matching 与 Diffusion
              </button>
              <button type="button" onClick={() => setDraft("帮我检索最新的医学图像生成 Flow Matching 论文") }>
                检索医学影像生成论文
              </button>
              <button type="button" onClick={() => setDraft("总结当前知识库中的实验室 GPU 使用规范") }>
                查询实验室知识库
              </button>
            </div>
          </section>
        )}

        {conversationId && messagesQuery.isLoading && (
          <div className="loading-row">正在恢复历史消息...</div>
        )}
        {conversationId && messagesQuery.isError && (
          <div className="error-banner">历史加载失败：{(messagesQuery.error as Error).message}</div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {optimisticUser && <UserBubble content={optimisticUser} />}
        {(streaming || streamText) && (
          <article className="message assistant-message streaming-message">
            <div className="avatar agent-avatar">E</div>
            <div className="message-body">
              <div className="message-meta">
                <strong>EduAgent</strong>
                <span className="streaming-dot">streaming</span>
              </div>
              {streamText ? (
                <div className="markdown"><ReactMarkdown>{streamText}</ReactMarkdown></div>
              ) : (
                <div className="thinking"><span /><span /><span /></div>
              )}
            </div>
          </article>
        )}
        {localError && <div className="error-banner">{localError}</div>}
      </div>

      <div className="composer-shell">
        <div className="composer">
          <textarea
            value={draft}
            placeholder="Ask EduAgent about research, papers, datasets, or lab knowledge..."
            rows={2}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
          />
          <button type="button" className="send-button" disabled={!draft.trim() || streaming} onClick={() => void send()}>
            {streaming ? "•••" : "↑"}
          </button>
        </div>
        <div className="composer-hint">Enter 发送 · Shift + Enter 换行 · 会话自动持久化</div>
      </div>
    </main>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "USER") return <UserBubble content={message.content} />;
  return (
    <article className="message assistant-message">
      <div className="avatar agent-avatar">E</div>
      <div className="message-body">
        <div className="message-meta">
          <strong>EduAgent</strong>
          {message.latencyMs !== null && <span>{(message.latencyMs / 1000).toFixed(1)}s</span>}
        </div>
        <div className="markdown"><ReactMarkdown>{message.content}</ReactMarkdown></div>
      </div>
    </article>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <article className="message user-message">
      <div className="avatar user-avatar">你</div>
      <div className="message-body">
        <div className="message-meta"><strong>You</strong></div>
        <p>{content}</p>
      </div>
    </article>
  );
}
