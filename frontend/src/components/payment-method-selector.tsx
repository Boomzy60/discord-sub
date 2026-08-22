"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  createCryptoCheckout,
  createPayPalCheckout,
  getCryptoCurrencies,
  type PaymentMethod,
} from "@/lib/api";
import type { CryptoCurrency } from "@/lib/types";
import { cn } from "@/lib/utils";

const METHODS: { id: PaymentMethod; label: string; description: string }[] = [
  { id: "paypal", label: "PayPal", description: "Pay with your PayPal balance or card" },
  { id: "crypto", label: "Crypto", description: "Pay with Bitcoin, Ethereum, and more" },
];

export function PaymentMethodSelector({ tierId }: { tierId: string }) {
  const [method, setMethod] = useState<PaymentMethod>("paypal");
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

      {method === "crypto" && (
        <div>
          {currencies === null && !currenciesError && (
            <p className="text-sm text-muted-foreground">Loading available currencies…</p>
          )}
          {currenciesError && <p className="text-sm text-destructive">{currenciesError}</p>}
          {cryptoUnavailable && (
            <p className="text-sm text-destructive">
              Crypto isn&apos;t available for this plan&apos;s price right now — please pay with
              PayPal instead.
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
