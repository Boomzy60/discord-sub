"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { createCryptoCheckout, createPayPalCheckout, type PaymentMethod } from "@/lib/api";
import { cn } from "@/lib/utils";

const METHODS: { id: PaymentMethod; label: string; description: string }[] = [
  { id: "paypal", label: "PayPal", description: "Pay with your PayPal balance or card" },
  { id: "crypto", label: "Crypto", description: "Pay with Bitcoin, Ethereum, and more" },
];

export function PaymentMethodSelector({ tierId }: { tierId: string }) {
  const [method, setMethod] = useState<PaymentMethod>("paypal");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCheckout() {
    setLoading(true);
    setError(null);
    try {
      const result =
        method === "paypal" ? await createPayPalCheckout(tierId) : await createCryptoCheckout(tierId);
      window.location.href = result.checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
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
