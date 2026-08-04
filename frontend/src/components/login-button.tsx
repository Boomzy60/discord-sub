import { Button } from "@/components/ui/button";
import { discordLoginUrl } from "@/lib/api";

export function LoginButton() {
  return (
    <Button asChild className="bg-primary text-primary-foreground hover:bg-primary/90">
      <a href={discordLoginUrl()}>Login with Discord</a>
    </Button>
  );
}
