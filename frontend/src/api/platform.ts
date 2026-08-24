import type {
  ChatMessage,
  Conversation,
  DocumentListResponse,
  DocumentType,
  DoneEvent,
  IngestResponse,
  KnowledgeSearchResponse,
  RouteEvent,
  StreamHandlers,
  TaskStatusResponse,
  ToolEvent,
} from "../types";

const API_BASE = "/api";

async function errorText(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) return `HTTP ${response.status}`;
  try {
    const parsed = JSON.parse(raw) as { message?: string; error?: string };
    return parsed.message ?? parsed.error ?? raw;
  } catch {
    return raw;
  }
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await errorText(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function listConversations(workspaceId = "demo"): Promise<Conversation[]> {
  return jsonRequest(`/conversations?workspaceId=${encodeURIComponent(workspaceId)}&limit=100`);
}

export function createConversation(workspaceId = "demo"): Promise<Conversation> {
  return jsonRequest("/conversations", {
    method: "POST",
    body: JSON.stringify({ workspaceId }),
  });
}

export function deleteConversation(id: string): Promise<void> {
  return jsonRequest(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function listMessages(conversationId: string): Promise<ChatMessage[]> {
  return jsonRequest(`/conversations/${encodeURIComponent(conversationId)}/messages`);
}

function parseData(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function dispatchEvent(eventName: string, rawData: string, handlers: StreamHandlers): void {
  const value = parseData(rawData);
  switch (eventName) {
    case "route":
      handlers.onRoute?.(value as RouteEvent);
      break;
    case "token":
      handlers.onToken?.(typeof value === "string" ? value : String(value ?? ""));
      break;
    case "tool_start":
      handlers.onToolStart?.(value as ToolEvent);
      break;
    case "tool_end":
      handlers.onToolEnd?.(value as ToolEvent);
      break;
    case "done":
      handlers.onDone?.(value as DoneEvent);
      break;
    case "error": {
      const message =
        typeof value === "object" && value && "message" in value
          ? String((value as { message: unknown }).message)
          : String(value ?? "Agent stream failed");
      handlers.onError?.(message);
      break;
    }
    default:
      break;
  }
}

function consumeSseBlock(block: string, handlers: StreamHandlers): void {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length > 0) {
    dispatchEvent(eventName, dataLines.join("\n"), handlers);
  }
}

export async function streamMessage(
  conversationId: string,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/conversations/${encodeURIComponent(conversationId)}/messages/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ content }),
      signal,
    },
  );

  if (!response.ok) {
    throw new Error(await errorText(response));
  }
  if (!response.body) {
    throw new Error("Streaming response body is unavailable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      consumeSseBlock(buffer.slice(0, boundary), handlers);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) consumeSseBlock(buffer, handlers);
}


export function listDocuments(
  workspaceId = "demo",
  documentType?: DocumentType | "all",
): Promise<DocumentListResponse> {
  const params = new URLSearchParams({ workspaceId });
  if (documentType && documentType !== "all") params.set("documentType", documentType);
  return jsonRequest(`/documents?${params.toString()}`);
}

export async function uploadDocument(input: {
  file: File;
  workspaceId?: string;
  documentId?: string;
  documentType: DocumentType;
}): Promise<IngestResponse> {
  const form = new FormData();
  form.set("file", input.file);
  form.set("workspaceId", input.workspaceId ?? "demo");
  form.set("documentType", input.documentType);
  if (input.documentId?.trim()) form.set("documentId", input.documentId.trim());

  const response = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) throw new Error(await errorText(response));
  return (await response.json()) as IngestResponse;
}

export function ingestTextDocument(input: {
  workspaceId?: string;
  documentId: string;
  source: string;
  text: string;
  documentType: DocumentType;
}): Promise<IngestResponse> {
  return jsonRequest("/documents/text", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId ?? "demo",
      document_id: input.documentId,
      source: input.source,
      text: input.text,
      document_type: input.documentType,
      metadata: {},
    }),
  });
}

export function getDocumentTask(taskId: string): Promise<TaskStatusResponse> {
  return jsonRequest(`/document-tasks/${encodeURIComponent(taskId)}`);
}

export function searchKnowledge(input: {
  workspaceId?: string;
  query: string;
  documentType?: DocumentType | "all";
  topK?: number;
}): Promise<KnowledgeSearchResponse> {
  const params = new URLSearchParams({
    workspaceId: input.workspaceId ?? "demo",
    query: input.query,
    topK: String(input.topK ?? 6),
  });
  if (input.documentType && input.documentType !== "all") {
    params.set("documentType", input.documentType);
  }
  return jsonRequest(`/knowledge/search?${params.toString()}`);
}
