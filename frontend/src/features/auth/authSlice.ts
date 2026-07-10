import { createSlice, createAsyncThunk, PayloadAction } from "@reduxjs/toolkit";
import { fetchApi } from "../../lib/api";

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

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

function sanitizeStorageData(value: string): string {
  if (!value) return value;
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function safeSetItem(key: string, value: string) {
  try {
    localStorage.setItem(key, sanitizeStorageData(value));
  } catch {
    /* localStorage unavailable */
  }
}

function safeGetItem(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeRemoveItem(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* localStorage unavailable */
  }
}

export const checkUser = createAsyncThunk(
  "auth/checkUser",
  async (_, { rejectWithValue }) => {
    const token = safeGetItem("accessToken");
    if (!token) {
      return rejectWithValue("No token");
    }
    try {
      const data = await fetchApi("/auth/me/", { requireAuth: true });
      return data as User;
    } catch {
      safeRemoveItem("accessToken");
      safeRemoveItem("refreshToken");
      return rejectWithValue("Failed to fetch user");
    }
  },
);

export const logoutAction = createAsyncThunk("auth/logout", async () => {
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
            body: JSON.stringify({ endpoint }),
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
});

export const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    loginTokens: (
      state,
      action: PayloadAction<{ access: string; refresh: string }>,
    ) => {
      safeSetItem("accessToken", action.payload.access);
      safeSetItem("refreshToken", action.payload.refresh);
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(checkUser.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(checkUser.fulfilled, (state, action) => {
        state.user = action.payload;
        state.isAuthenticated = true;
        state.isLoading = false;
      })
      .addCase(checkUser.rejected, (state) => {
        state.user = null;
        state.isAuthenticated = false;
        state.isLoading = false;
      })
      .addCase(logoutAction.fulfilled, (state) => {
        state.user = null;
        state.isAuthenticated = false;
      });
  },
});

export const { loginTokens } = authSlice.actions;

export default authSlice.reducer;
