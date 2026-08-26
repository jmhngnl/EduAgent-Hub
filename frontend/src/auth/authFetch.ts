import { refreshSession } from "./api";
import { useAuthStore } from "./useAuthStore";

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = refreshSession()
      .then((session) => {
        useAuthStore.getState().setSession(session);
        return session.accessToken;
      })
      .catch(() => {
        useAuthStore.getState().clearSession();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function withAuth(init?: RequestInit): RequestInit {
  const state = useAuthStore.getState();
  const headers = new Headers(init?.headers ?? {});
  if (state.accessToken) headers.set("Authorization", `Bearer ${state.accessToken}`);
  if (state.activeWorkspaceId) headers.set("X-Workspace-Id", state.activeWorkspaceId);
  return { ...init, credentials: "include", headers };
}

export async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let response = await fetch(input, withAuth(init));
  if (response.status !== 401) return response;

  const token = await refreshAccessToken();
  if (!token) return response;
  response = await fetch(input, withAuth(init));
  return response;
}
