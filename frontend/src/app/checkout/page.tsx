import Link from "next/link";
import { redirect } from "next/navigation";

import { PaymentMethodSelector } from "@/components/payment-method-selector";
import { discordLoginUrl, getTiers } from "@/lib/api";
import { getCurrentUser } from "@/lib/session";

export default async function CheckoutPage(props: PageProps<"/checkout">) {
  const searchParams = await props.searchParams;
  const tierId = typeof searchParams.tier === "string" ? searchParams.tier : undefined;

  const user = await getCurrentUser();
  if (!user) {
    redirect(discordLoginUrl());
  }

  const tiers = await getTiers();
  const tier = tierId ? tiers.find((candidate) => candidate.id === tierId) : undefined;

  if (!tier) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <h1 className="text-2xl font-bold">Plan not found</h1>
        <p className="mt-3 text-muted-foreground">
          That plan isn&apos;t available anymore. Head back to{" "}
          <Link href="/pricing" className="text-primary underline">
            pricing
          </Link>{" "}
          to pick one.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <h1 className="text-2xl font-bold">Checkout</h1>
      <div className="mt-6 flex items-center justify-between rounded-lg border border-border bg-card p-4">
        <span className="font-medium">{tier.name}</span>
        <span className="font-bold">
          ${tier.price.toFixed(2)}{" "}
          <span className="font-normal text-muted-foreground">
            / {tier.billing_period === "QUARTERLY" ? "3 months" : "month"}
          </span>
        </span>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">Choose how you&apos;d like to pay.</p>
      <div className="mt-4">
        <PaymentMethodSelector tierId={tier.id} />
      </div>
    </div>
  );
}
