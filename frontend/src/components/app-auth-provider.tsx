"use client";

import {
  ClerkProvider,
  SignInButton,
  UserButton,
  useAuth,
  useUser,
} from "@clerk/nextjs";
import { LogIn, UserRound } from "lucide-react";
import {
  createContext,
  type ReactNode,
  useContext,
  useLayoutEffect,
} from "react";

import { setAuthTokenProvider } from "@/lib/api";

type AppAuthState = {
  configured: boolean;
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
};

const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim() || "";
const guestAuthState: AppAuthState = {
  configured: false,
  isLoaded: true,
  isSignedIn: false,
  userId: null,
};
const AppAuthContext = createContext<AppAuthState>(guestAuthState);

function ClerkAuthBridge({ children }: { children: ReactNode }) {
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();

  useLayoutEffect(() => {
    setAuthTokenProvider(isSignedIn ? () => getToken() : null);
    return () => setAuthTokenProvider(null);
  }, [getToken, isSignedIn, userId]);

  return (
    <AppAuthContext.Provider
      value={{
        configured: true,
        isLoaded,
        isSignedIn: Boolean(isSignedIn),
        userId: userId ?? null,
      }}
    >
      {children}
    </AppAuthContext.Provider>
  );
}

export function AppAuthProvider({ children }: { children: ReactNode }) {
  if (!publishableKey) {
    return (
      <AppAuthContext.Provider value={guestAuthState}>
        {children}
      </AppAuthContext.Provider>
    );
  }

  return (
    <ClerkProvider publishableKey={publishableKey}>
      <ClerkAuthBridge>{children}</ClerkAuthBridge>
    </ClerkProvider>
  );
}

export function useAppAuth(): AppAuthState {
  return useContext(AppAuthContext);
}

function ConfiguredAccountControl() {
  const { isLoaded, isSignedIn, user } = useUser();

  if (!isLoaded) {
    return <div className="account-status muted">正在读取账号</div>;
  }

  if (!isSignedIn) {
    return (
      <SignInButton mode="modal">
        <button className="account-sign-in" type="button">
          <LogIn size={16} />
          登录并同步历史
        </button>
      </SignInButton>
    );
  }

  return (
    <div className="account-profile">
      <UserButton />
      <span>
        <strong>{user.fullName || user.primaryEmailAddress?.emailAddress || "已登录"}</strong>
        <small>历史已绑定账号</small>
      </span>
    </div>
  );
}

export function AccountControl() {
  const { configured } = useAppAuth();
  if (configured) return <ConfiguredAccountControl />;

  return (
    <div className="account-profile guest">
      <UserRound size={20} />
      <span>
        <strong>访客模式</strong>
        <small>历史保存在当前浏览器</small>
      </span>
    </div>
  );
}
