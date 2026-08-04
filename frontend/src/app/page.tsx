import { LogIn, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import { LoginButton } from "@/components/login-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getCurrentUser } from "@/lib/session";

const STEPS = [
  {
    icon: LogIn,
    title: "Login with Discord",
    description: "Sign in with your Discord account.",
  },
  {
    icon: Sparkles,
    title: "Choose your plan",
    description: "Pick the tier that fits you. Pay monthly with PayPal or crypto.",
  },
  {
    icon: ShieldCheck,
    title: "Get instant access",
    description: "Your role is granted automatically the moment payment clears.",
  },
];

export default async function HomePage() {
  const user = await getCurrentUser();

  return (
    <div className="mx-auto max-w-5xl px-4">
      <section className="flex flex-col items-center gap-6 py-20 text-center sm:py-28">
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight sm:text-5xl">
          Unlock premium roles in <span className="text-primary">our Discord community</span>
        </h1>
        <p className="max-w-xl text-muted-foreground sm:text-lg">
          Subscribe in a few clicks and get your Discord role automatically.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Button
            render={<Link href="/pricing" />}
            nativeButton={false}
            size="lg"
            className="bg-black px-6 text-white hover:bg-black/85"
          >
            View plans
          </Button>
          {!user && <LoginButton />}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 pb-20 sm:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, description }) => (
          <Card key={title}>
            <CardContent className="flex flex-col items-center gap-3 pt-6 text-center">
              <div className="flex size-10 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Icon className="size-5" />
              </div>
              <h2 className="font-semibold">{title}</h2>
              <p className="text-sm text-muted-foreground">{description}</p>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
