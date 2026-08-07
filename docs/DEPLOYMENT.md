# Production Deployment

Step-by-step guide to putting the stack live on a real domain, written for a first deploy.
Follow the sections in order — each one builds on the last.

## 0. What you need before starting

- A domain name (you already have one from Wix).
- A VPS from [Cloudzy](https://cloudzy.com) (or any Ubuntu VPS). 2 vCPU / 2-4GB RAM is plenty.
- A free [Cloudflare](https://cloudflare.com) account (recommended for DNS).
- Live (non-sandbox) credentials for PayPal and NOWPayments.
- Your production Discord server + bot set up — see
  [MIGRATION_TO_PROD_DISCORD.md](./MIGRATION_TO_PROD_DISCORD.md) for that part specifically.

Nothing here requires touching application code — production config is entirely env vars
and the two files added in this milestone (`Caddyfile`, `docker-compose.prod.yml`).

## 1. Create the VPS

1. Order a VPS from Cloudzy. Choose **Ubuntu 22.04**.
2. Note its public IPv4 address — you'll need it for DNS in step 3.
3. SSH into it: `ssh root@YOUR_VPS_IP`

## 2. Install Docker on the VPS

```bash
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin git
```

Set up a basic firewall so only SSH, HTTP, and HTTPS are reachable:

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```

## 3. Point your domain at the VPS

Your domain is registered at Wix, but Wix's own DNS panel is limited, so the recommended
path is to let **Cloudflare** manage DNS instead (Wix stays the registrar — you're only
changing who answers DNS queries for the domain).

1. Sign up at Cloudflare and click **Add a Site**, enter your domain.
2. Pick the Free plan. Cloudflare scans existing DNS records, then gives you two
   nameservers (e.g. `ada.ns.cloudflare.com`, `bob.ns.cloudflare.com`).
3. In Wix: go to your domain's settings → **DNS / Nameservers** → switch from Wix
   nameservers to **custom nameservers** → paste in Cloudflare's two nameservers.
4. Wait for Cloudflare to detect the change (usually minutes, can take a few hours).
   Cloudflare emails you once it's active.
5. In Cloudflare's DNS tab, add two records, both **DNS only** (grey cloud, not orange —
   this matters, see note below):

   | Type | Name | Content       |
   |------|------|---------------|
   | A    | @    | YOUR_VPS_IP   |
   | A    | api  | YOUR_VPS_IP   |

   `yourdomain.com` will serve the website, `api.yourdomain.com` will serve the backend.

> **Why "DNS only" and not Cloudflare's orange-cloud proxy?** Caddy (step 5) issues its
> own free HTTPS certificates automatically, which requires it to see real visitor
> connections directly. Cloudflare's proxy sits in the way of that unless you configure
> its SSL mode correctly. Keeping records DNS-only for now is the simplest path — you can
> enable the proxy later once the site is confirmed working.

## 4. Get the code onto the VPS

```bash
git clone <your-repo-url> discord-sub
cd discord-sub
cp .env.example .env
```

Edit `.env` with production values. Compared to your local `.env`, change at least:

| Variable | Production value |
|---|---|
| `ENVIRONMENT` | `production` |
| `BACKEND_BASE_URL` | `https://api.yourdomain.com` |
| `FRONTEND_BASE_URL` | `https://yourdomain.com` |
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.yourdomain.com` |
| `DISCORD_REDIRECT_URI` | `https://api.yourdomain.com/auth/discord/callback` |
| `JWT_SECRET` | a new long random value (`openssl rand -hex 32`) — never reuse the dev one |
| `PAYPAL_MODE` | `live` |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` / `PAYPAL_WEBHOOK_ID` | from a **live** PayPal REST app, not sandbox |
| `NOWPAYMENTS_API_KEY` / `NOWPAYMENTS_IPN_SECRET` | from your live NOWPayments dashboard |
| `DISCORD_*` (client id/secret, guild id, role ids, bot token) | your production Discord app/server values — see the migration doc |

Also update the two domains in the `Caddyfile` (`yourdomain.com`, `api.yourdomain.com`)
and the `email` field at the top, then commit or just edit directly on the VPS.

## 5. Set up live payment credentials

- **PayPal**: in the [PayPal Developer Dashboard](https://developer.paypal.com), create
  (or switch to) a **Live** app to get a live client ID/secret. Under your live app's
  webhooks, add `https://api.yourdomain.com/webhooks/paypal` subscribed to the payment
  capture events, and copy the resulting Webhook ID into `PAYPAL_WEBHOOK_ID`.
- **NOWPayments**: in your NOWPayments dashboard, switch out of sandbox, copy your live
  API key, and set your IPN callback URL to `https://api.yourdomain.com/webhooks/nowpayments`.
  Copy the IPN secret into `NOWPAYMENTS_IPN_SECRET`.

## 6. Deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend alembic upgrade head
```

First boot takes a little longer since Caddy needs to request certificates and the
frontend needs to run its production build. Watch progress with:

```bash
docker compose logs -f caddy
docker compose ps
```

Once `caddy` logs show certificates obtained, visit `https://yourdomain.com` — you
should see the site over HTTPS with a valid padlock.

## 7. Redeploying after future code changes

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

All services use `restart: unless-stopped`, so the stack also survives a VPS reboot
without manual intervention.

## Troubleshooting

- **Caddy can't get a certificate**: DNS hasn't propagated yet, or port 80/443 is
  blocked. Confirm `dig yourdomain.com` resolves to your VPS IP, and that `ufw status`
  shows 80/443 allowed.
- **Login redirects fail / CORS errors in the browser console**: double-check
  `DISCORD_REDIRECT_URI`, `FRONTEND_BASE_URL`, and `NEXT_PUBLIC_API_BASE_URL` all use
  `https://` and the correct domain — a mismatch here is the most common cause.
- **Webhook not activating subscriptions**: check `docker compose logs backend` for
  signature verification failures, and confirm the webhook URLs configured in the PayPal/
  NOWPayments dashboards exactly match `https://api.yourdomain.com/webhooks/...`.
