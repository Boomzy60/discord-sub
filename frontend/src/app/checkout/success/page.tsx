import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function CheckoutSuccessPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <CheckCircle2 className="mx-auto size-12 text-primary" />
      <h1 className="mt-4 text-2xl font-bold">Payment received</h1>
      <p className="mt-3 text-muted-foreground">
        We&apos;re confirming your payment now. Your Discord role is granted automatically as
        soon as it clears — no further action needed.
      </p>
      <Button render={<Link href="/dashboard" />} className="mt-6">
        Go to dashboard
      </Button>
    </div>
  );
}
