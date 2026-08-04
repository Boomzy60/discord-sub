export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function discordLoginUrl(): string {
  return `${API_BASE_URL}/auth/discord/login`;
}

export function logoutUrl(): string {
  return `${API_BASE_URL}/auth/logout`;
}
