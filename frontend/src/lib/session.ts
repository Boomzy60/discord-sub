import "server-only";
import { cookies } from "next/headers";

import { API_BASE_URL } from "@/lib/api";
import type { ApiEnvelope, Subscription, User } from "@/lib/types";

export async function getCurrentUser(): Promise<User | null> {
  const cookieStore = await cookies();
  const session = cookieStore.get("session");

  if (!session) {
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/users/me`, {
      headers: { Cookie: `session=${session.value}` },
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const body = (await response.json()) as ApiEnvelope<User>;
    return body.data;
  } catch (err) {
    // Backend unreachable — fail open to "logged out" instead of crashing every
    // page (auth state is checked on every layout render), but log it so a
    // real outage is visible in the container logs rather than silently hidden.
    console.error("getCurrentUser: failed to reach backend", err);
    return null;
  }
}

export async function getMySubscriptions(): Promise<Subscription[]> {
  const cookieStore = await cookies();
  const session = cookieStore.get("session");

  if (!session) {
    return [];
  }

  try {
    const response = await fetch(`${API_BASE_URL}/subscriptions/me`, {
      headers: { Cookie: `session=${session.value}` },
      cache: "no-store",
    });

    if (!response.ok) {
      return [];
    }

    const body = (await response.json()) as ApiEnvelope<Subscription[]>;
    return body.data ?? [];
  } catch (err) {
    console.error("getMySubscriptions: failed to reach backend", err);
    return [];
  }
}
