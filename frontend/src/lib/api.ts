import type { ApiEnvelope, Tier } from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function discordLoginUrl(): string {
  return `${API_BASE_URL}/auth/discord/login`;
}

export function logoutUrl(): string {
  return `${API_BASE_URL}/auth/logout`;
}

export async function getTiers(): Promise<Tier[]> {
  const response = await fetch(`${API_BASE_URL}/tiers`, { cache: "no-store" });

  if (!response.ok) {
    return [];
  }

  const body = (await response.json()) as ApiEnvelope<Tier[]>;
  return body.data ?? [];
}

export type PaymentMethod = "paypal" | "crypto";

export interface CheckoutResult {
  checkout_url: string;
  payment_id: string;
}

async function startCheckout(method: PaymentMethod, tierId: string): Promise<CheckoutResult> {
  const response = await fetch(`${API_BASE_URL}/payments/${method}/checkout/${tierId}`, {
    method: "POST",
    credentials: "include",
  });

  const body = (await response.json()) as ApiEnvelope<CheckoutResult>;
  if (!response.ok || !body.data) {
    const message = typeof body.error === "string" ? body.error : "Failed to start checkout";
    throw new Error(message);
  }

  return body.data;
}

export function createPayPalCheckout(tierId: string): Promise<CheckoutResult> {
  return startCheckout("paypal", tierId);
}

export function createCryptoCheckout(tierId: string): Promise<CheckoutResult> {
  return startCheckout("crypto", tierId);
}
