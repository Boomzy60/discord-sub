import "server-only";
import { cookies } from "next/headers";

import { API_BASE_URL } from "@/lib/api";
import type { ApiEnvelope, User } from "@/lib/types";

export async function getCurrentUser(): Promise<User | null> {
  const cookieStore = await cookies();
  const session = cookieStore.get("session");

  if (!session) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/users/me`, {
    headers: { Cookie: `session=${session.value}` },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  const body = (await response.json()) as ApiEnvelope<User>;
  return body.data;
}
