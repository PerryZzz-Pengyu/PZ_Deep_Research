"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

export type AppAuthState = {
  configured: boolean;
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
};

type AppAuthContextValue = AppAuthState & {
  updateAuth: (next: Omit<AppAuthState, "configured">) => void;
};

const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim() || "";
const initialAuthState: AppAuthState = {
  configured: Boolean(publishableKey),
  // Authentication is optional. The product starts in guest mode while Clerk
  // initializes so an external auth outage cannot freeze research.
  isLoaded: true,
  isSignedIn: false,
  userId: null,
};

const AppAuthContext = createContext<AppAuthContextValue>({
  ...initialAuthState,
  updateAuth: () => undefined,
});

export function AppAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initialAuthState);
  const updateAuth = useCallback((next: Omit<AppAuthState, "configured">) => {
    setState((current) => {
      const updated = { configured: Boolean(publishableKey), ...next };
      return current.configured === updated.configured
        && current.isLoaded === updated.isLoaded
        && current.isSignedIn === updated.isSignedIn
        && current.userId === updated.userId
        ? current
        : updated;
    });
  }, []);
  const value = useMemo(() => ({ ...state, updateAuth }), [state, updateAuth]);

  return <AppAuthContext.Provider value={value}>{children}</AppAuthContext.Provider>;
}

export function useAppAuth(): AppAuthState {
  const context = useContext(AppAuthContext);
  return {
    configured: context.configured,
    isLoaded: context.isLoaded,
    isSignedIn: context.isSignedIn,
    userId: context.userId,
  };
}

export function useAppAuthRuntime() {
  const { configured, updateAuth } = useContext(AppAuthContext);
  return { configured, publishableKey, updateAuth };
}
