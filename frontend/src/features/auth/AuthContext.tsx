/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { fetchApi } from "../../lib/api";

type User = {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  avatar_url?: string | null;
  timezone?: string;
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
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  function safeGetItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }
  function safeSetItem(key: string, value: string) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* localStorage unavailable */
    }
  }
  function safeRemoveItem(key: string) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* localStorage unavailable */
    }
  }

  const login = (tokens: { access: string; refresh: string }) => {
    safeSetItem("accessToken", tokens.access);
    safeSetItem("refreshToken", tokens.refresh);
    checkUser();
  };

  const logout = async () => {
    try {
      if ("serviceWorker" in navigator && "PushManager" in window) {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          const endpoint = sub.endpoint;
          await sub.unsubscribe();
          try {
            await fetchApi("/notifications/push/unsubscribe/", {
              method: "POST",
              requireAuth: true,
              body: JSON.stringify({ endpoint })
            });
          } catch (e) {
            console.error("Failed to notify backend of push unsubscribe", e);
          }
        }
      }
    } catch (e) {
      console.error("Error unsubscribing push on logout", e);
    }
    
    safeRemoveItem("accessToken");
    safeRemoveItem("refreshToken");
    setUser(null);
  };

  const checkUser = useCallback(async () => {
    try {
      const token = safeGetItem("accessToken");
      if (!token) {
        setUser(null);
        return;
      }

      // Some setups can temporarily fail right after login (network hiccup / token not yet accepted).
      // Avoid logging the user out on the first failure.
      try {
        const data = await fetchApi("/auth/me/");
        setUser(data);
        return;
      } catch {
        const data = await fetchApi("/auth/me/");
        setUser(data);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    
    
   checkUser();
  }, [checkUser]);
  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        checkUser,
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
