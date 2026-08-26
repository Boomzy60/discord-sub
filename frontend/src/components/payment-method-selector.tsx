"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  createCryptoCheckout,
  createPayPalCheckout,
  createStripeCheckout,
  type PaymentMethod,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// PayPal account is temporarily restricted (pending bank review) — re-enable by
// flipping this back once it's resolved.
const PAYPAL_ENABLED = false;

const METHODS: { id: PaymentMethod; label: string; description: string }[] = [
  ...(PAYPAL_ENABLED
    ? [{ id: "paypal" as const, label: "PayPal", description: "Pay with your PayPal balance or card" }]
    : []),
  { id: "stripe", label: "Card", description: "Pay with a debit or credit card via Stripe" },
  { id: "crypto", label: "Crypto", description: "Pay with Bitcoin, Ethereum, and more" },
];

export function PaymentMethodSelector({ tierId }: { tierId: string }) {
  const [method, setMethod] = useState<PaymentMethod>(METHODS[0].id);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCheckout() {
    setLoading(true);
    setError(null);
    try {
      const result =
        method === "paypal"
          ? await createPayPalCheckout(tierId)
          : method === "stripe"
            ? await createStripeCheckout(tierId)
            : await createCryptoCheckout(tierId);
      window.location.href = result.checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className={cn("grid gap-3", METHODS.length > 1 ? "grid-cols-2" : "grid-cols-1")}>
        {METHODS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setMethod(option.id)}
            className={cn(
              "rounded-lg border p-4 text-left transition-colors",
              method === option.id
                ? "border-primary bg-primary/5 ring-1 ring-primary"
                : "border-border hover:bg-muted"
            )}
          >
            <div className="font-medium">{option.label}</div>
            <div className="text-sm text-muted-foreground">{option.description}</div>
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button className="w-full" disabled={loading} onClick={handleCheckout}>
        {loading ? "Redirecting…" : `Pay with ${METHODS.find((option) => option.id === method)?.label}`}
      </Button>
    </div>
  );
}
