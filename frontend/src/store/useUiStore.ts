import { create } from "zustand";
import type { Citation, DoneEvent, RouteEvent } from "../types";

type ToolState = { name: string; status: "running" | "done" };

type TraceState = {
  taskRoute: string | null;
  taskRouteLabel: string | null;
  skill: string | null;
  tools: ToolState[];
  citations: Citation[];
  latencyMs: number | null;
  error: string | null;
  streaming: boolean;
};

type UiStore = TraceState & {
  selectedConversationId: string | null;
  setSelectedConversationId: (id: string | null) => void;
  resetTrace: () => void;
  setStreaming: (value: boolean) => void;
  setRoute: (data: RouteEvent) => void;
  toolStarted: (name: string) => void;
  toolFinished: (name: string) => void;
  streamDone: (data: DoneEvent) => void;
  streamError: (message: string) => void;
  restoreTrace: (value: Partial<TraceState>) => void;
};

const EMPTY_TRACE: TraceState = {
  taskRoute: null,
  taskRouteLabel: null,
  skill: null,
  tools: [],
  citations: [],
  latencyMs: null,
  error: null,
  streaming: false,
};

export const useUiStore = create<UiStore>((set) => ({
  ...EMPTY_TRACE,
  selectedConversationId: localStorage.getItem("eduagent-v2-selected-conversation"),
  setSelectedConversationId: (id) => {
    if (id) localStorage.setItem("eduagent-v2-selected-conversation", id);
    else localStorage.removeItem("eduagent-v2-selected-conversation");
    set({ selectedConversationId: id });
  },
  resetTrace: () => set({ ...EMPTY_TRACE }),
  setStreaming: (streaming) => set({ streaming }),
  setRoute: (data) =>
    set({
      taskRoute: data.task_route,
      taskRouteLabel: data.task_route_label,
      skill: data.skill,
    }),
  toolStarted: (name) =>
    set((state) => ({
      tools: state.tools.some((item) => item.name === name)
        ? state.tools.map((item) =>
            item.name === name ? { ...item, status: "running" as const } : item,
          )
        : [...state.tools, { name, status: "running" as const }],
    })),
  toolFinished: (name) =>
    set((state) => ({
      tools: state.tools.some((item) => item.name === name)
        ? state.tools.map((item) =>
            item.name === name ? { ...item, status: "done" as const } : item,
          )
        : [...state.tools, { name, status: "done" as const }],
    })),
  streamDone: (data) =>
    set({
      taskRoute: data.task_route,
      taskRouteLabel: data.task_route_label,
      skill: data.skill,
      tools: data.tool_calls.map((name) => ({ name, status: "done" as const })),
      citations: data.citations ?? [],
      latencyMs: data.latency_ms ?? null,
      error: null,
      streaming: false,
    }),
  streamError: (message) => set({ error: message, streaming: false }),
  restoreTrace: (value) => set({ ...EMPTY_TRACE, ...value }),
}));
