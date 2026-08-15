import Image from "next/image";
import Link from "next/link";

import { LoginButton } from "@/components/login-button";
import { UserMenu } from "@/components/user-menu";
import type { User } from "@/lib/types";

export function Navbar({ user }: { user: User | null }) {
  return (
    <header className="border-b border-border bg-background/80 backdrop-blur sticky top-0 z-10">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center">
          <Image src="/logo.png" alt="Kiyomi Studio" width={36} height={36} className="rounded-lg" priority />
          <span className="sr-only">Kiyomi Studio</span>
        </Link>
        <nav className="flex items-center gap-6 text-sm font-medium">
          <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
            Pricing
          </Link>
          {user ? <UserMenu user={user} /> : <LoginButton />}
        </nav>
      </div>
    </header>
  );
}
