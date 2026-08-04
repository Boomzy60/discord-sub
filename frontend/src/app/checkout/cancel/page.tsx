import { XCircle } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function CheckoutCancelPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <XCircle className="mx-auto size-12 text-muted-foreground" />
      <h1 className="mt-4 text-2xl font-bold">Checkout cancelled</h1>
      <p className="mt-3 text-muted-foreground">
        No payment was made. You can pick a plan again whenever you&apos;re ready.
      </p>
      <Button render={<Link href="/pricing" />} className="mt-6">
        Back to pricing
      </Button>
    </div>
  );
}
