// @refresh reset
/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useEffect,
  useCallback,
} from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { checkUser, loginTokens, logoutAction } from "./authSlice";

type User = {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  avatar_url?: string | null;
  cover_image_url?: string | null;
  bio?: string;
  bio_html?: string;
  timezone?: string;
  twitter_url?: string;
  linkedin_url?: string;
  github_url?: string;
  receive_weekly_digest?: boolean;
};

type AuthContextType = {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (tokens: { access: string; refresh: string }) => void;
  logout: () => void;
  checkUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const dispatch = useAppDispatch();
  const { user, isAuthenticated, isLoading } = useAppSelector(
    (state) => state.auth,
  );

  const login = (tokens: { access: string; refresh: string }) => {
    dispatch(loginTokens(tokens));
    dispatch(checkUser());
  };

  const logout = async () => {
    try {
      sessionStorage.setItem("userLoggedOut", "true");
    } catch (e) {}
    dispatch(logoutAction());
  };

  const performCheckUser = useCallback(async () => {
    dispatch(checkUser());
  }, [dispatch]);

  useEffect(() => {
    performCheckUser();
  }, [performCheckUser]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        login,
        logout,
        checkUser: performCheckUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
