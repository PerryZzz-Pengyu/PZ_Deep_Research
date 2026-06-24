import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Controlled return value for Clerk's useAuth across tests.
const authState: { isLoaded: boolean; isSignedIn: boolean } = {
  isLoaded: true,
  isSignedIn: false,
};

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  SignInButton: ({ children }: { children: ReactNode }) => (
    <div data-testid="sign-in-button">{children}</div>
  ),
  UserButton: () => <div data-testid="user-button" />,
  useAuth: () => ({
    getToken: vi.fn(),
    isLoaded: authState.isLoaded,
    isSignedIn: authState.isSignedIn,
    userId: authState.isSignedIn ? "user_test" : null,
  }),
  useUser: () => ({ user: null }),
}));

vi.mock("@heroui/react", () => ({
  Button: ({ children }: { children: ReactNode }) => <button>{children}</button>,
}));

vi.mock("lucide-react", () => ({ LogIn: () => null }));

vi.mock("@/lib/api", () => ({ setAuthTokenProvider: vi.fn() }));

vi.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: { wb: { accountSignIn: "登录并同步历史", field: { scholar: "学者" }, syncedAcross: "" } } }),
}));

import { ClerkSignInControl } from "@/components/clerk-controls";

const renderControl = () =>
  render(
    <ClerkSignInControl fallback={<span>fallback</span>} label="登录" publishableKey="pk_test_123" />,
  );

afterEach(() => {
  authState.isLoaded = true;
  authState.isSignedIn = false;
});

describe("ClerkSignInControl nav button", () => {
  it("renders the sign-in modal trigger when the user is signed out", () => {
    authState.isSignedIn = false;
    renderControl();

    expect(screen.getByTestId("sign-in-button")).toBeInTheDocument();
    expect(screen.queryByTestId("user-button")).not.toBeInTheDocument();
  });

  it("renders the account avatar (UserButton) instead of a sign-in modal when already signed in", () => {
    // Regression: opening <SignIn/> while signed in throws
    // cannot_render_single_session_enabled under Clerk single-session mode.
    authState.isSignedIn = true;
    renderControl();

    expect(screen.getByTestId("user-button")).toBeInTheDocument();
    expect(screen.queryByTestId("sign-in-button")).not.toBeInTheDocument();
  });
});
