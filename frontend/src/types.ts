export type Conversation = {
  id: string;
  userId: string | null;
  workspaceId: string;
  title: string;
  status: string;
  createdAt: string;
  updatedAt: string;
};

export type ChatRole = "USER" | "ASSISTANT" | "SYSTEM";

export type ChatMessage = {
  id: string;
  conversationId: string;
  role: ChatRole;
  content: string;
  taskRoute: string | null;
  skillName: string | null;
  toolCallsJson: string | null;
  citationsJson: string | null;
  tokenUsageJson: string | null;
  latencyMs: number | null;
  createdAt: string;
};

export type Citation = {
  document_id: string;
  source: string;
  chunk_id: string;
  score: number;
  citation_type?: "knowledge" | "paper";
  url?: string | null;
  title?: string | null;
  year?: number | null;
};

export type RouteEvent = {
  task_route: string;
  task_route_label: string;
  skill: string | null;
};

export type DoneEvent = RouteEvent & {
  session_id: string;
  citations: Citation[];
  tool_calls: string[];
  guarded: boolean;
  platform_message_id?: string;
  latency_ms?: number;
};

export type ToolEvent = {
  name: string;
};

export type StreamHandlers = {
  onRoute?: (data: RouteEvent) => void;
  onToken?: (token: string) => void;
  onToolStart?: (data: ToolEvent) => void;
  onToolEnd?: (data: ToolEvent) => void;
  onDone?: (data: DoneEvent) => void;
  onError?: (message: string) => void;
};
