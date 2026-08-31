import type { ApiEnvelope, CryptoCurrency, Tier } from "@/lib/types";

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
    throw new Error(`Failed to load plans (status ${response.status})`);
  }

  const body = (await response.json()) as ApiEnvelope<Tier[]>;
  return body.data ?? [];
}

export type PaymentMethod = "paypal" | "stripe" | "crypto";

export interface CheckoutResult {
  checkout_url: string;
  payment_id: string;
}

async function startCheckout(
  method: PaymentMethod,
  tierId: string,
  body?: Record<string, unknown>
): Promise<CheckoutResult> {
  const response = await fetch(`${API_BASE_URL}/payments/${method}/checkout/${tierId}`, {
    method: "POST",
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  const responseBody = (await response.json()) as ApiEnvelope<CheckoutResult>;
  if (!response.ok || !responseBody.data) {
    const message =
      typeof responseBody.error === "string" ? responseBody.error : "Failed to start checkout";
    throw new Error(message);
  }

  return responseBody.data;
}

export function createPayPalCheckout(tierId: string): Promise<CheckoutResult> {
  return startCheckout("paypal", tierId);
}

export function createStripeCheckout(tierId: string): Promise<CheckoutResult> {
  return startCheckout("stripe", tierId);
}

export function createCryptoCheckout(tierId: string, payCurrency: string): Promise<CheckoutResult> {
  return startCheckout("crypto", tierId, { pay_currency: payCurrency });
}

export async function getCryptoCurrencies(tierId: string): Promise<CryptoCurrency[]> {
  const response = await fetch(`${API_BASE_URL}/payments/crypto/currencies/${tierId}`, {
    credentials: "include",
  });

  const body = (await response.json()) as ApiEnvelope<CryptoCurrency[]>;
  if (!response.ok || !body.data) {
    const message = typeof body.error === "string" ? body.error : "Failed to load currencies";
    throw new Error(message);
  }

  return body.data;
}
