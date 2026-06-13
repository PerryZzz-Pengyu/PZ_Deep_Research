"use client";

import { Button } from "@heroui/react";
import {
  ClerkProvider,
  SignInButton,
  UserButton,
  useAuth,
  useUser,
} from "@clerk/nextjs";
import { LogIn } from "lucide-react";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

import type { AppAuthState } from "@/components/app-auth-provider";
import { setAuthTokenProvider } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const AUTH_FALLBACK_TIMEOUT_MS = 3_000;

type AuthUpdate = (next: Omit<AppAuthState, "configured">) => void;

function ClerkAccountContent({
  onReady,
  updateAuth,
}: {
  onReady: () => void;
  updateAuth: AuthUpdate;
}) {
  const { t } = useI18n();
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const { user } = useUser();

  useEffect(() => {
    if (!isLoaded) return;
    onReady();
    setAuthTokenProvider(isSignedIn ? () => getToken() : null);
    updateAuth({
      isLoaded: true,
      isSignedIn: Boolean(isSignedIn),
      userId: userId ?? null,
    });
    return () => setAuthTokenProvider(null);
  }, [getToken, isLoaded, isSignedIn, onReady, updateAuth, userId]);

  if (!isLoaded) return null;

  if (!isSignedIn) {
    return (
      <SignInButton mode="modal">
        <Button className="account-sign-in" variant="secondary">
          <LogIn size={16} />
          {t.wb.accountSignIn}
        </Button>
      </SignInButton>
    );
  }

  const displayName = user?.fullName || user?.primaryEmailAddress?.emailAddress || t.wb.field.scholar;
  return (
    <div className="account-profile">
      <UserButton />
      <span>
        <strong>{displayName}</strong>
        <small>{t.wb.syncedAcross}</small>
      </span>
    </div>
  );
}

export function ClerkAccountControl({
  fallback,
  publishableKey,
  updateAuth,
}: {
  fallback: ReactNode;
  publishableKey: string;
  updateAuth: AuthUpdate;
}) {
  const [ready, setReady] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const handleReady = useCallback(() => setReady(true), []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setTimedOut(true);
      updateAuth({ isLoaded: true, isSignedIn: false, userId: null });
    }, AUTH_FALLBACK_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [updateAuth]);

  return (
    <>
      {!ready && timedOut ? fallback : null}
      <ClerkProvider publishableKey={publishableKey}>
        <ClerkAccountContent onReady={handleReady} updateAuth={updateAuth} />
      </ClerkProvider>
      {!ready && !timedOut ? <div className="account-status" aria-live="polite" /> : null}
    </>
  );
}

function ClerkSignInContent({ label, onReady }: { label: string; onReady: () => void }) {
  const { isLoaded } = useAuth();

  useEffect(() => {
    if (isLoaded) onReady();
  }, [isLoaded, onReady]);

  if (!isLoaded) return null;
  return (
    <SignInButton mode="modal">
      <Button className="nav-signin" size="sm" variant="ghost">
        <LogIn size={15} />
        {label}
      </Button>
    </SignInButton>
  );
}

export function ClerkSignInControl({
  fallback,
  label,
  publishableKey,
}: {
  fallback: ReactNode;
  label: string;
  publishableKey: string;
}) {
  const [ready, setReady] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const handleReady = useCallback(() => setReady(true), []);

  useEffect(() => {
    const timer = window.setTimeout(() => setTimedOut(true), AUTH_FALLBACK_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <>
      {!ready && timedOut ? fallback : null}
      <ClerkProvider publishableKey={publishableKey}>
        <ClerkSignInContent label={label} onReady={handleReady} />
      </ClerkProvider>
    </>
  );
}
