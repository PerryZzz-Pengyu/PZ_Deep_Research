"use client";

import dynamic from "next/dynamic";
import { Button } from "@heroui/react";
import { LogIn, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAppAuthRuntime } from "@/components/app-auth-provider";
import { useI18n } from "@/lib/i18n";

const ClerkAccountControl = dynamic(
  () => import("@/components/clerk-controls").then((module) => module.ClerkAccountControl),
  { ssr: false },
);

const ClerkSignInControl = dynamic(
  () => import("@/components/clerk-controls").then((module) => module.ClerkSignInControl),
  { ssr: false },
);

function GuestAccountControl() {
  const { t } = useI18n();
  return (
    <div className="account-profile guest">
      <span className="avatar"><UserRound size={18} /></span>
      <span>
        <strong>{t.wb.accountGuest}</strong>
        <small>{t.wb.accountGuestDesc}</small>
      </span>
    </div>
  );
}

export function AccountControl() {
  const runtime = useAppAuthRuntime();
  if (!runtime.configured) return <GuestAccountControl />;

  return (
    <ClerkAccountControl
      fallback={<GuestAccountControl />}
      publishableKey={runtime.publishableKey}
      updateAuth={runtime.updateAuth}
    />
  );
}

export function SignInControl() {
  const { t } = useI18n();
  const router = useRouter();
  const runtime = useAppAuthRuntime();
  if (!runtime.configured) {
    return (
      <Button className="nav-signin" size="sm" variant="ghost" onPress={() => router.push("/workbench")}>
        <LogIn size={15} />
        {t.nav.signIn}
      </Button>
    );
  }

  return (
    <ClerkSignInControl
      fallback={(
        <Button className="nav-signin" size="sm" variant="ghost" onPress={() => router.push("/workbench")}>
          <LogIn size={15} />
          {t.nav.signIn}
        </Button>
      )}
      label={t.nav.signIn}
      publishableKey={runtime.publishableKey}
    />
  );
}
