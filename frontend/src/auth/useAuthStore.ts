import { create } from "zustand";
import type { AuthSessionResponse, MeResponse, PlatformUser, WorkspaceMembership } from "./types";

const STORAGE_KEY = "eduagent-v2-auth";
const WORKSPACE_KEY = "eduagent-v2-workspace";

type Persisted = {
  accessToken: string | null;
  user: PlatformUser | null;
  workspaces: WorkspaceMembership[];
};

function readPersisted(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { accessToken: null, user: null, workspaces: [] };
    const value = JSON.parse(raw) as Partial<Persisted>;
    return {
      accessToken: value.accessToken ?? null,
      user: value.user ?? null,
      workspaces: value.workspaces ?? [],
    };
  } catch {
    return { accessToken: null, user: null, workspaces: [] };
  }
}

const initial = readPersisted();

type AuthState = Persisted & {
  activeWorkspaceId: string | null;
  bootstrapped: boolean;
  setSession: (session: AuthSessionResponse) => void;
  setMe: (me: MeResponse) => void;
  setAccessToken: (token: string) => void;
  setActiveWorkspaceId: (workspaceId: string | null) => void;
  clearSession: () => void;
  setBootstrapped: (value: boolean) => void;
};

function chooseWorkspace(workspaces: WorkspaceMembership[], preferred: string | null): string | null {
  if (preferred && workspaces.some((item) => item.id === preferred)) return preferred;
  return workspaces[0]?.id ?? null;
}

function persist(state: Persisted): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export const useAuthStore = create<AuthState>((set, get) => ({
  ...initial,
  activeWorkspaceId: chooseWorkspace(initial.workspaces, localStorage.getItem(WORKSPACE_KEY)),
  bootstrapped: false,
  setSession: (session) => {
    const next = {
      accessToken: session.accessToken,
      user: session.user,
      workspaces: session.workspaces,
    };
    const activeWorkspaceId = chooseWorkspace(session.workspaces, get().activeWorkspaceId);
    persist(next);
    if (activeWorkspaceId) localStorage.setItem(WORKSPACE_KEY, activeWorkspaceId);
    else localStorage.removeItem(WORKSPACE_KEY);
    set({ ...next, activeWorkspaceId });
  },
  setMe: (me) => {
    const next = {
      accessToken: get().accessToken,
      user: me.user,
      workspaces: me.workspaces,
    };
    const activeWorkspaceId = chooseWorkspace(me.workspaces, get().activeWorkspaceId);
    persist(next);
    if (activeWorkspaceId) localStorage.setItem(WORKSPACE_KEY, activeWorkspaceId);
    else localStorage.removeItem(WORKSPACE_KEY);
    set({ ...next, activeWorkspaceId });
  },
  setAccessToken: (accessToken) => {
    const next = { accessToken, user: get().user, workspaces: get().workspaces };
    persist(next);
    set({ accessToken });
  },
  setActiveWorkspaceId: (activeWorkspaceId) => {
    if (activeWorkspaceId) localStorage.setItem(WORKSPACE_KEY, activeWorkspaceId);
    else localStorage.removeItem(WORKSPACE_KEY);
    set({ activeWorkspaceId });
  },
  clearSession: () => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(WORKSPACE_KEY);
    set({ accessToken: null, user: null, workspaces: [], activeWorkspaceId: null });
  },
  setBootstrapped: (bootstrapped) => set({ bootstrapped }),
}));
