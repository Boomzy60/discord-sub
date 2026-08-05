import { Sparkles } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { discordAvatarUrl, discordDisplayName } from "@/lib/discord";
import { getCurrentUser } from "@/lib/session";

export default async function DashboardPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/");
  }

  const displayName = discordDisplayName(user);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          <Avatar size="lg">
            <AvatarImage src={discordAvatarUrl(user)} alt={displayName} />
            <AvatarFallback>{displayName.slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Welcome back, {displayName}</h1>
            <p className="mt-1 text-muted-foreground">
              You&apos;re signed in with Discord. Pick a plan to unlock your role.
            </p>
          </div>
          <Button
            render={<Link href="/pricing" />}
            nativeButton={false}
            size="lg"
            className="mt-2 bg-black px-6 text-white hover:bg-black/85"
          >
            <Sparkles className="size-4" />
            View plans
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
