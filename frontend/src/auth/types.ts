export type PlatformUser = {
  id: string;
  username: string;
  displayName: string;
};

export type WorkspaceMembership = {
  id: string;
  name: string;
  role: "OWNER" | "ADMIN" | "MEMBER" | "VIEWER";
};

export type WorkspaceMember = {
  userId: string;
  username: string;
  displayName: string;
  role: "OWNER" | "ADMIN" | "MEMBER" | "VIEWER";
};

export type AuthSessionResponse = {
  accessToken: string;
  tokenType: "Bearer";
  expiresInSeconds: number;
  user: PlatformUser;
  workspaces: WorkspaceMembership[];
};

export type MeResponse = {
  user: PlatformUser;
  workspaces: WorkspaceMembership[];
};
