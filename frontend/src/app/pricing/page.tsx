import { TierCard } from "@/components/tier-card";
import { getTiers } from "@/lib/api";
import { getCurrentUser } from "@/lib/session";

export default async function PricingPage() {
  const [tiers, user] = await Promise.all([getTiers(), getCurrentUser()]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <div className="mb-12 text-center">
        <h1 className="text-4xl font-bold tracking-tight">Choose your plan</h1>
        <p className="mt-3 text-muted-foreground">
          Unlock premium roles in our Discord community.
        </p>
      </div>
      {tiers.length === 0 ? (
        <p className="text-center text-muted-foreground">
          No plans available yet. Check back soon.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {tiers.map((tier) => (
            <TierCard
              key={tier.id}
              tier={tier}
              isLoggedIn={user !== null}
              highlighted={tier.name === "Bronze (3 Month)"}
            />
          ))}
        </div>
      )}
    </div>
  );
}
