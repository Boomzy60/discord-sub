import type { Metadata } from "next";
import "./globals.css";

import { Navbar } from "@/components/navbar";
import { getCurrentUser } from "@/lib/session";

export const metadata: Metadata = {
  title: "Kiyomi Studio",
  description: "Subscribe to unlock premium roles in our Discord community.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const user = await getCurrentUser();

  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <Navbar user={user} />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
