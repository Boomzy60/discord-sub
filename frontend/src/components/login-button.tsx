import { Button } from "@/components/ui/button";
import { discordLoginUrl } from "@/lib/api";

export function LoginButton() {
  return (
    <Button
      render={<a href={discordLoginUrl()} />}
      nativeButton={false}
      size="lg"
      className="bg-black px-6 text-white hover:bg-black/85"
    >
      Login with Discord
    </Button>
  );
}
