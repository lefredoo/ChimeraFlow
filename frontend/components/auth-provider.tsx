"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { clearSession, loadSession, saveSession } from "../lib/auth/token-storage";
import { setUnauthorizedHandler } from "../lib/services/api-client";
import { fetchCurrentUser, login, type LoginResult } from "../lib/services/auth-service";

export type AuthState =
  | { status: "checking" }
  | { status: "anonymous" }
  | { status: "authenticated"; email: string };

interface AuthContextValue {
  state: AuthState;
  signIn: (email: string, password: string) => Promise<LoginResult>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [state, setState] = useState<AuthState>({ status: "checking" });

  useEffect(() => {
    let cancelled = false;
    // Any 401 from the API (expired or invalid token) sends the user back to the login page
    setUnauthorizedHandler(() => setState({ status: "anonymous" }));

    const session = loadSession();
    if (session === null) {
      setState({ status: "anonymous" });
    } else {
      // The stored token is only trusted once the API accepts it. An unreachable
      // API does not refute it, so a flaky network does not log the user out.
      fetchCurrentUser().then((result) => {
        if (cancelled || result.state === "unauthorized") {
          return;
        }
        setState({
          status: "authenticated",
          email: result.state === "authenticated" ? result.email : session.email,
        });
      });
    }
    return () => {
      cancelled = true;
      setUnauthorizedHandler(null);
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    const result = await login(email, password);
    if (result.state === "success") {
      saveSession(result.session);
      setState({ status: "authenticated", email: result.session.email });
    }
    return result;
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setState({ status: "anonymous" });
  }, []);

  const value = useMemo(() => ({ state, signIn, signOut }), [state, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return context;
}
