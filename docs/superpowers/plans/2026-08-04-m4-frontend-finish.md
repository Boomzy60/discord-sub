# M4 Frontend Finish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Milestone 4 (frontend skeleton & login UI) so the Discord OAuth login flow works end-to-end without hitting a 404, per `docs/superpowers/specs/2026-08-04-m4-frontend-finish-design.md`.

**Architecture:** Next.js App Router, server components fetching session state via the existing `getCurrentUser()` helper (`frontend/src/lib/session.ts`), which reads the `session` cookie and calls the backend's `GET /users/me`. Four page-level changes plus one pre-existing bug fix that currently blocks the build.

**Tech Stack:** Next.js 16 (App Router), TypeScript (strict), Tailwind CSS v4, shadcn/ui components built on `@base-ui/react` primitives.

## Global Constraints

- No backend changes — only files under `frontend/src/`.
- No new npm dependencies — use what's already installed.
- Reuse the existing pink/purple theme (`frontend/src/app/globals.css`) and existing shadcn primitives (`Button`, `Card`, `Avatar`, `DropdownMenu`) — no new design tokens or component libraries.
- No frontend test runner is configured (confirmed: no `test` script in `frontend/package.json`, no Jest/Vitest config). Per the spec's Testing section, verification is `npx tsc --noEmit` (fast type-check) after each task, plus one end-to-end curl-based check in the final task. Do not add a test runner — that's out of scope for this milestone.
- All commands below run with `frontend/` as the working directory unless stated otherwise.
- Follow the Base UI `render`-prop composition pattern already used elsewhere in the codebase (see Task 1) — never `asChild` (that's a Radix convention; this project uses `@base-ui/react`, which does not support it).

---

### Task 1: Fix pre-existing Base UI `render`-prop bug (blocks the build)

**Context:** `npx tsc --noEmit` currently fails with 2 errors — `frontend/src/components/login-button.tsx` and `frontend/src/components/user-menu.tsx` both use `<Button asChild>`, but this project's Button (`frontend/src/components/ui/button.tsx`) wraps `@base-ui/react/button`, which has no `asChild` prop — it uses a `render` prop instead (confirmed in `frontend/node_modules/@base-ui/react/docs/react/handbook/composition.md` and `.../docs/react/components/button.md`). The bundled Base UI docs explicitly say: *"Links (`<a>`) have their own semantics and should not be rendered as buttons through the `render` prop... style the `<a>` element directly with CSS rather than using the Button component."* So the two call sites need two different fixes:

- `login-button.tsx` wraps an `<a>` — per the docs, don't use `Button`/`render` at all; style the anchor directly with the exported `buttonVariants` class function.
- `user-menu.tsx`'s `DropdownMenuTrigger` wraps a `Button` (not a link) — this is exactly the supported composition case, so it becomes `<DropdownMenuTrigger render={<Button .../>}>`, with children staying on `DropdownMenuTrigger` (per the composition doc's `<Menu.Trigger render={<MyButton .../>}>Open menu</Menu.Trigger>` example — the render element supplies the target tag, the outer component keeps the children).

**Files:**
- Modify: `frontend/src/components/login-button.tsx`
- Modify: `frontend/src/components/user-menu.tsx`

**Interfaces:**
- Consumes: `buttonVariants` (named export from `frontend/src/components/ui/button.tsx`, already exists: `export { Button, buttonVariants }`).
- Produces: no new exports; `LoginButton` and `UserMenu` keep their existing signatures (`LoginButton()`, `UserMenu({ user }: { user: User })`).

- [ ] **Step 1: Confirm the baseline failure**

Run: `cd frontend && npx tsc --noEmit`
Expected: FAIL with 2 errors, both `TS2322 ... Property 'asChild' does not exist`, in `login-button.tsx` and `user-menu.tsx`.

- [ ] **Step 2: Fix `login-button.tsx`**

Replace the entire file with:

```tsx
import { buttonVariants } from "@/components/ui/button";
import { discordLoginUrl } from "@/lib/api";

export function LoginButton() {
  return (
    <a href={discordLoginUrl()} className={buttonVariants()}>
      Login with Discord
    </a>
  );
}
```

- [ ] **Step 3: Fix `user-menu.tsx`**

Replace this block (currently lines 36-46):

```tsx
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="flex items-center gap-2 px-2">
          <Avatar className="size-8">
            <AvatarImage src={avatarUrl(user)} alt={displayName} />
            <AvatarFallback>{displayName.slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <span className="hidden sm:inline">{displayName}</span>
        </Button>
      </DropdownMenuTrigger>
```

with:

```tsx
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="ghost" className="flex items-center gap-2 px-2" />}
      >
        <Avatar className="size-8">
          <AvatarImage src={avatarUrl(user)} alt={displayName} />
          <AvatarFallback>{displayName.slice(0, 2).toUpperCase()}</AvatarFallback>
        </Avatar>
        <span className="hidden sm:inline">{displayName}</span>
      </DropdownMenuTrigger>
```

(Leave the rest of the file — `DropdownMenuContent` and its items — untouched.)

- [ ] **Step 4: Verify the fix**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS with no errors (empty output, exit code 0).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/login-button.tsx frontend/src/components/user-menu.tsx
git commit -m "fix(frontend): use Base UI render prop instead of asChild"
```

---

### Task 2: Shared Discord avatar helper + `/dashboard` page

**Context:** The OAuth callback (`backend/app/api/routes/auth.py`, `discord_callback`) redirects to `{frontend_base_url}/dashboard` unconditionally after a successful login — this route must exist or every real login 404s. `user-menu.tsx` already has an `avatarUrl(user)` helper; the dashboard page needs the identical logic, so it's extracted into a shared module rather than duplicated (per `CLAUDE.md`'s "Avoid duplication").

**Files:**
- Create: `frontend/src/lib/discord.ts`
- Modify: `frontend/src/components/user-menu.tsx`
- Create: `frontend/src/app/dashboard/page.tsx`

**Interfaces:**
- Consumes: `User` type (`frontend/src/lib/types.ts`), `getCurrentUser()` (`frontend/src/lib/session.ts`, returns `Promise<User | null>`), `Card`/`CardContent`/`CardHeader`/`CardTitle` (`frontend/src/components/ui/card.tsx`), `Avatar`/`AvatarImage`/`AvatarFallback` (`frontend/src/components/ui/avatar.tsx`), `redirect` (`next/navigation`).
- Produces: `discordAvatarUrl(user: User): string | undefined` (named export from `frontend/src/lib/discord.ts`) — later tasks/pages needing a user's avatar should import this instead of re-deriving the CDN URL.

- [ ] **Step 1: Create the shared helper**

Create `frontend/src/lib/discord.ts`:

```ts
import type { User } from "@/lib/types";

export function discordAvatarUrl(user: User): string | undefined {
  if (!user.avatar) return undefined;
  return `https://cdn.discordapp.com/avatars/${user.discord_id}/${user.avatar}.png`;
}
```

- [ ] **Step 2: Update `user-menu.tsx` to use it**

Remove the local function (currently lines 18-21):

```tsx
function avatarUrl(user: User): string | undefined {
  if (!user.avatar) return undefined;
  return `https://cdn.discordapp.com/avatars/${user.discord_id}/${user.avatar}.png`;
}
```

Add to the top import block:

```tsx
import { discordAvatarUrl } from "@/lib/discord";
```

Replace the one usage, `src={avatarUrl(user)}`, with `src={discordAvatarUrl(user)}`.

- [ ] **Step 3: Verify types still check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no errors) — `User` is still imported in `user-menu.tsx` for the component's prop type, so its import stays.

- [ ] **Step 4: Create the dashboard page**

Create `frontend/src/app/dashboard/page.tsx`:

```tsx
import { redirect } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { discordAvatarUrl } from "@/lib/discord";
import { getCurrentUser } from "@/lib/session";

export default async function DashboardPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/");
  }

  const displayName = user.global_name ?? user.username;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-12">
      <Card>
        <CardContent className="flex items-center gap-4">
          <Avatar className="size-12">
            <AvatarImage src={discordAvatarUrl(user)} alt={displayName} />
            <AvatarFallback>{displayName.slice(0, 2).toUpperCase()}</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-sm text-muted-foreground">Welcome back</p>
            <p className="text-xl font-semibold">{displayName}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground">
          You don&apos;t have an active subscription yet. Visit the pricing
          page to get started.
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no errors).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/discord.ts frontend/src/components/user-menu.tsx frontend/src/app/dashboard/page.tsx
git commit -m "feat(frontend): add dashboard page and shared avatar helper"
```

---

### Task 3: Home page

**Context:** `frontend/src/app/page.tsx` is still the unmodified `create-next-app` template. Replace it with a real landing page: hero copy, a login/dashboard CTA depending on auth state, and a static 3-card tier teaser (no real pricing data — that's M5/M6).

**Files:**
- Modify: `frontend/src/app/page.tsx`

**Interfaces:**
- Consumes: `getCurrentUser()` (`@/lib/session`), `LoginButton` (`@/components/login-button`), `buttonVariants` (`@/components/ui/button`), `Card`/`CardHeader`/`CardTitle`/`CardDescription` (`@/components/ui/card`), `Link` (`next/link`).
- Produces: default export `Home` page at `/` (unchanged route, new implementation).

- [ ] **Step 1: Replace the page**

Replace the entire contents of `frontend/src/app/page.tsx` with:

```tsx
import Link from "next/link";

import { LoginButton } from "@/components/login-button";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getCurrentUser } from "@/lib/session";

const TIERS = [
  { name: "Bronze", blurb: "Get started with core community access." },
  { name: "Silver", blurb: "Unlock additional channels and perks." },
  { name: "Gold", blurb: "The full experience, all access included." },
];

export default async function Home() {
  const user = await getCurrentUser();

  return (
    <div className="mx-auto flex max-w-5xl flex-col items-center gap-16 px-4 py-24 text-center">
      <div className="flex flex-col items-center gap-6">
        <h1 className="bg-gradient-to-r from-primary to-accent bg-clip-text text-4xl font-bold text-transparent sm:text-5xl">
          Unlock your Discord community
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          Subscribe to a membership tier and get instant, automatic access to
          exclusive roles in our Discord server.
        </p>
        {user ? (
          <Link href="/dashboard" className={buttonVariants()}>
            Go to Dashboard
          </Link>
        ) : (
          <LoginButton />
        )}
      </div>

      <div className="grid w-full grid-cols-1 gap-6 md:grid-cols-3">
        {TIERS.map((tier) => (
          <Card key={tier.name} className="text-left">
            <CardHeader>
              <CardTitle>{tier.name}</CardTitle>
              <CardDescription>{tier.blurb}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat(frontend): replace boilerplate home page with real landing page"
```

---

### Task 4: `/pricing` stub page

**Context:** `Navbar` (`frontend/src/components/navbar.tsx:18-20`) already links to `/pricing`; the route doesn't exist yet, so it 404s. Real content (fetching live tiers) is Milestone 6 (already specced in `docs/superpowers/specs/2026-08-04-pricing-page-design.md` but not yet implemented, since it depends on the not-yet-built M5 backend). For M4, this is a placeholder only.

**Files:**
- Create: `frontend/src/app/pricing/page.tsx`

**Interfaces:**
- Consumes: `Card`/`CardHeader`/`CardTitle`/`CardDescription` (`@/components/ui/card`).
- Produces: default export `PricingPage` at `/pricing`.

- [ ] **Step 1: Create the page**

Create `frontend/src/app/pricing/page.tsx`:

```tsx
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function PricingPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Pricing tiers coming soon</CardTitle>
          <CardDescription>
            We&apos;re putting the finishing touches on our subscription
            plans. Check back shortly.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pricing/page.tsx
git commit -m "feat(frontend): add pricing page placeholder"
```

---

### Task 5: `/admin` stub page

**Context:** `UserMenu` (`frontend/src/components/user-menu.tsx`) shows an "Admin" menu item linking to `/admin` when `user.is_admin` is true; the route doesn't exist yet. Real content is Milestone 13. For M4, this is an admin-gated placeholder.

**Files:**
- Create: `frontend/src/app/admin/page.tsx`

**Interfaces:**
- Consumes: `getCurrentUser()` (`@/lib/session`), `redirect` (`next/navigation`), `Card`/`CardHeader`/`CardTitle`/`CardDescription` (`@/components/ui/card`).
- Produces: default export `AdminPage` at `/admin`.

- [ ] **Step 1: Create the page**

Create `frontend/src/app/admin/page.tsx`:

```tsx
import { redirect } from "next/navigation";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getCurrentUser } from "@/lib/session";

export default async function AdminPage() {
  const user = await getCurrentUser();

  if (!user || !user.is_admin) {
    redirect("/");
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Admin dashboard coming soon</CardTitle>
          <CardDescription>
            Tier and subscriber management tools are on the way.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/admin/page.tsx
git commit -m "feat(frontend): add admin page placeholder with admin-only gate"
```

---

### Task 6: Integration verification

**Context:** No frontend test runner is configured (out of scope to add one now). Verify the whole milestone works by building for production and hitting every route with an unauthenticated request — the state every route sees before a real Discord login. A real, authenticated end-to-end click-through requires configured `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET` and a live browser session, which can't be scripted here — flag that as a manual follow-up.

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Full production build**

Run: `cd frontend && npm run build`
Expected: build succeeds (exit code 0), no type or lint errors.

- [ ] **Step 2: Start the dev server and wait for it to be ready**

```bash
cd frontend
npm run dev > dev-server.log 2>&1 &
DEV_PID=$!
for i in $(seq 1 30); do
  curl -sf http://localhost:3000/ >/dev/null 2>&1 && break
  sleep 1
done
```

- [ ] **Step 3: Check every route as an unauthenticated visitor**

```bash
curl -s http://localhost:3000/ | grep -q "Unlock your Discord community" \
  && echo "HOME OK" || echo "HOME FAIL"

curl -s http://localhost:3000/pricing | grep -q "Pricing tiers coming soon" \
  && echo "PRICING OK" || echo "PRICING FAIL"

curl -sI http://localhost:3000/dashboard | grep -qi "^location: /$" \
  && echo "DASHBOARD REDIRECT OK" || echo "DASHBOARD FAIL"

curl -sI http://localhost:3000/admin | grep -qi "^location: /$" \
  && echo "ADMIN REDIRECT OK" || echo "ADMIN FAIL"
```

Expected: all four print `OK`. `/dashboard` and `/admin` redirect to `/` because there's no `session` cookie — `getCurrentUser()` returns `null` without even calling the backend (it short-circuits when the cookie is absent), so this check needs no backend running.

- [ ] **Step 4: Stop the dev server**

```bash
kill $DEV_PID 2>/dev/null || true
rm -f dev-server.log
```

- [ ] **Step 5: Report the manual follow-up**

No commit for this task (verification only). Tell the user: automated checks confirm the unauthenticated paths and the build; a real login click-through (Discord OAuth → `/dashboard` → `UserMenu` appears → logout → back to `/`) still needs to be done manually against a configured `DISCORD_CLIENT_ID`/`DISCORD_CLIENT_SECRET` in a real browser, since that can't be scripted headlessly.

---

## Self-Review Notes

- **Spec coverage:** all 4 spec sections (home, dashboard, pricing, admin) map 1:1 to Tasks 2-5. The spec didn't anticipate the `asChild`/Base UI bug — that surfaced during planning (baseline `tsc --noEmit` run) and is a build-blocker for the whole milestone, so it's Task 1, ahead of everything else.
- **Type consistency:** `discordAvatarUrl(user: User): string | undefined` (Task 2) is the same signature used in Task 2's own dashboard page — no other task references it.
- **No placeholders:** every step has literal file contents or literal commands; no "TBD" or "similar to Task N" shortcuts.
