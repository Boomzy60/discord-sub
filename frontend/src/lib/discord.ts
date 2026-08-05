import type { User } from "@/lib/types";

export function discordAvatarUrl(user: User): string | undefined {
  if (!user.avatar) return undefined;
  return `https://cdn.discordapp.com/avatars/${user.discord_id}/${user.avatar}.png`;
}

export function discordDisplayName(user: User): string {
  return user.global_name ?? user.username;
}
