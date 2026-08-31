import { Check } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { discordLoginUrl } from "@/lib/api";
import type { Tier } from "@/lib/types";
import { cn } from "@/lib/utils";

const BILLING_LABEL: Record<Tier["billing_period"], string> = {
  MONTHLY: "month",
  QUARTERLY: "3 months",
  YEARLY: "year",
  LIFETIME: "lifetime",
};

export function TierCard({
  tier,
  isLoggedIn,
  highlighted,
}: {
  tier: Tier;
  isLoggedIn: boolean;
  highlighted: boolean;
}) {
  const features = (tier.description ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <Card className={cn("flex flex-col", highlighted && "ring-2 ring-accent md:-translate-y-2")}>
      <CardHeader>
        {highlighted && (
          <Badge className="mb-2 w-fit bg-accent text-accent-foreground">Most Popular</Badge>
        )}
        <CardTitle className="text-xl">{tier.name}</CardTitle>
        <CardDescription>
          <span className="text-3xl font-bold text-foreground">${tier.price.toFixed(2)}</span>
          <span className="text-muted-foreground"> / {BILLING_LABEL[tier.billing_period]}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <ul className="space-y-2 text-sm">
          {features.map((feature, index) => (
            <li key={index} className="flex items-start gap-2">
              <Check className="mt-0.5 size-4 shrink-0 text-primary" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter>
        {isLoggedIn ? (
          <Button
            render={<Link href={`/checkout?tier=${tier.id}`} />}
            nativeButton={false}
            className="w-full"
          >
            Subscribe
          </Button>
        ) : (
          <Button render={<a href={discordLoginUrl()} />} nativeButton={false} className="w-full">
            Subscribe
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
