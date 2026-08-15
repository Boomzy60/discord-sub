# Migrating from the Test Discord Server to the Client's Real Server

The platform was built and tested against a throwaway Discord server. This is the
checklist for pointing it at the client's real server instead. Every difference between
"test" and "production" here is an environment variable — no code changes are needed.

## 1. Decide whether to reuse the Discord application

You can keep the same Discord application (same `DISCORD_CLIENT_ID` /
`DISCORD_CLIENT_SECRET`) — a Discord application isn't tied to one server, so this is the
simplest option and works fine for production.

If you'd rather start clean, create a new application at the
[Discord Developer Portal](https://discord.com/developers/applications) instead, and use
its client ID/secret going forward.

Either way, in the application's **OAuth2 → General** settings, add the production
redirect URL:

```
https://api.kiyomistudio.com/auth/discord/callback
```

You can remove the old `http://localhost:8000/...` redirect once production is confirmed
working.

## 2. Invite the bot to the client's real server

Build an invite URL from the Developer Portal's **OAuth2 → URL Generator**:

- Scopes: `bot`
- Bot permissions: `Manage Roles` (plus `View Channels` / `Send Messages` if you're using
  the subscription log channel)

Open the generated URL, pick the client's real server, and authorize it.

**Important:** in the server's role list, drag the bot's own role **above** the three
subscription tier roles. Discord bots can only assign/remove roles positioned below their
own role — this is the most common cause of "role assignment silently does nothing."

## 3. Create (or confirm) the three tier roles

Create the three subscription roles in the real server if they don't already exist, then
copy each role's ID (enable Developer Mode in Discord settings, right-click the role →
Copy Role ID).

## 4. Update environment variables

On the VPS, edit `.env`:

| Variable | Set to |
|---|---|
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | from step 1 |
| `DISCORD_REDIRECT_URI` | `https://api.kiyomistudio.com/auth/discord/callback` |
| `DISCORD_BOT_TOKEN` | the bot token for the application from step 1 |
| `DISCORD_GUILD_ID` | the client's real server ID |
| `DISCORD_ROLE_ID_TIER_1` / `_TIER_2` / `_TIER_3` | the role IDs from step 3 |
| `DISCORD_LOG_CHANNEL_ID` | (optional) a channel ID in the real server, or leave blank |

## 5. Restart the affected services

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend bot
```

## 6. Verify end-to-end

1. Log in on the live site with a Discord account that's a member of the real server.
2. Run a real (or minimum-amount) purchase through checkout.
3. Confirm the correct role appears on that member in the real server within a few
   seconds of payment confirmation.
4. Optionally, manually expire a test subscription row and confirm the scheduled job
   (Milestone 12) removes the role again.

If a step fails, `docker compose logs bot` and `docker compose logs backend` are the
first places to look — role assignment failures (missing permission, role ordering) show
up there.
