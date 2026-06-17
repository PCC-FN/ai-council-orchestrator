import { api } from "./client";

export type AuthUser = {
  id: string;
  username: string;
  display_name: string;
  role: string;
};

export type AuthPermissions = {
  role: string;
  can_write: boolean;
  can_view: boolean;
  is_admin: boolean;
  is_authenticated: boolean;
};

export const authApi = {
  me: () => api<AuthUser>("/auth/me"),
  permissions: () => api<AuthPermissions>("/auth/me/permissions"),
  createUser: (body: { username: string; role: string; display_name?: string }) =>
    api<{ user: AuthUser; token: string }>("/auth/users", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
