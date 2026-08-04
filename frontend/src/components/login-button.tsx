import { Button } from "@/components/ui/button";
import { discordLoginUrl } from "@/lib/api";

export function LoginButton() {
  return (
    <Button
      render={<a href={discordLoginUrl()} />}
      className="bg-primary text-primary-foreground hover:bg-primary/90"
    >
      Login with Discord
    </Button>
  );
}
