import type { AuthSessionResponse, MeResponse, WorkspaceMember, WorkspaceMembership } from "./types";
import { useAuthStore } from "./useAuthStore";

const API = "/api";

async function errorMessage(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) return `HTTP ${response.status}`;
  try {
    const parsed = JSON.parse(raw) as { message?: string; detail?: string; error?: string };
    return parsed.message ?? parsed.detail ?? parsed.error ?? raw;
  } catch {
    return raw;
  }
}

async function authJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<AuthSessionResponse> {
  return authJson("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
}

export async function register(username: string, password: string, displayName: string): Promise<AuthSessionResponse> {
  return authJson("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password, displayName }),
  });
}

export async function refreshSession(): Promise<AuthSessionResponse> {
  return authJson("/auth/refresh", { method: "POST" });
}

export async function logout(): Promise<void> {
  try {
    await authJson<void>("/auth/logout", { method: "POST" });
  } finally {
    useAuthStore.getState().clearSession();
  }
}

export async function me(accessToken: string): Promise<MeResponse> {
  const response = await fetch(`${API}/auth/me`, {
    credentials: "include",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as MeResponse;
}

export async function listWorkspaces(): Promise<WorkspaceMembership[]> {
  const { authFetch } = await import("./authFetch");
  const response = await authFetch("/api/workspaces");
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as WorkspaceMembership[];
}

export async function createWorkspace(name: string): Promise<WorkspaceMembership> {
  const { authFetch } = await import("./authFetch");
  const response = await authFetch("/api/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as WorkspaceMembership;
}

export async function listWorkspaceMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  const { authFetch } = await import("./authFetch");
  const response = await authFetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/members`);
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as WorkspaceMember[];
}

export async function upsertWorkspaceMember(
  workspaceId: string,
  username: string,
  role: "ADMIN" | "MEMBER" | "VIEWER",
): Promise<WorkspaceMember> {
  const { authFetch } = await import("./authFetch");
  const response = await authFetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/members`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, role }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  return (await response.json()) as WorkspaceMember;
}

export async function removeWorkspaceMember(workspaceId: string, userId: string): Promise<void> {
  const { authFetch } = await import("./authFetch");
  const response = await authFetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error(await errorMessage(response));
}
