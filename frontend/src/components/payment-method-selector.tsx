"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  createCryptoCheckout,
  createPayPalCheckout,
  createStripeCheckout,
  getCryptoCurrencies,
  type PaymentMethod,
} from "@/lib/api";
import type { CryptoCurrency } from "@/lib/types";
import { cn } from "@/lib/utils";

// PayPal account is temporarily restricted (pending bank review) — re-enable by
// flipping this back once it's resolved.
const PAYPAL_ENABLED = false;
// Card payments disabled for now — re-enable by flipping this back once ready.
const STRIPE_ENABLED = false;

const METHODS: { id: PaymentMethod; label: string; description: string }[] = [
  ...(PAYPAL_ENABLED
    ? [{ id: "paypal" as const, label: "PayPal", description: "Pay with your PayPal balance or card" }]
    : []),
  ...(STRIPE_ENABLED
    ? [{ id: "stripe" as const, label: "Card", description: "Pay with a debit or credit card via Stripe" }]
    : []),
  { id: "crypto", label: "Crypto", description: "Pay with Bitcoin, Ethereum, and more" },
];

export function PaymentMethodSelector({ tierId }: { tierId: string }) {
  const [method, setMethod] = useState<PaymentMethod>(METHODS[0].id);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [currencies, setCurrencies] = useState<CryptoCurrency[] | null>(null);
  const [currenciesError, setCurrenciesError] = useState<string | null>(null);
  const [selectedCurrency, setSelectedCurrency] = useState<string>("");

  useEffect(() => {
    if (method !== "crypto" || currencies !== null || currenciesError) return;

    getCryptoCurrencies(tierId)
      .then((result) => {
        setCurrencies(result);
        setSelectedCurrency(result[0]?.code ?? "");
      })
      .catch((err) => {
        setCurrenciesError(err instanceof Error ? err.message : "Failed to load currencies");
      });
  }, [method, tierId, currencies, currenciesError]);

  async function handleCheckout() {
    setLoading(true);
    setError(null);
    try {
      const result =
        method === "paypal"
          ? await createPayPalCheckout(tierId)
          : method === "stripe"
            ? await createStripeCheckout(tierId)
            : await createCryptoCheckout(tierId, selectedCurrency);
      window.location.href = result.checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  const cryptoUnavailable = method === "crypto" && currencies !== null && currencies.length === 0;
  const payDisabled =
    loading || (method === "crypto" && (!selectedCurrency || currenciesError !== null || cryptoUnavailable));

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

      {method === "crypto" && (
        <div>
          {currencies === null && !currenciesError && (
            <p className="text-sm text-muted-foreground">Loading available currencies…</p>
          )}
          {currenciesError && <p className="text-sm text-destructive">{currenciesError}</p>}
          {cryptoUnavailable && (
            <p className="text-sm text-destructive">
              {"Crypto needs at least $12. Try the 3 month plan instead."}
            </p>
          )}
          {currencies !== null && currencies.length > 0 && (
            <select
              value={selectedCurrency}
              onChange={(event) => setSelectedCurrency(event.target.value)}
              className="w-full rounded-lg border border-border bg-card p-3 text-sm"
            >
              {currencies.map((currency) => (
                <option key={currency.code} value={currency.code}>
                  {currency.label}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button className="w-full" disabled={payDisabled} onClick={handleCheckout}>
        {loading ? "Redirecting…" : `Pay with ${METHODS.find((option) => option.id === method)?.label}`}
      </Button>
    </div>
  );
}
