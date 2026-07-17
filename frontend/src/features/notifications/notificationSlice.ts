import { createSlice, PayloadAction, createAsyncThunk } from "@reduxjs/toolkit";
import { fetchApi } from "../../lib/api";

export interface AppNotification {
  id: number;
  notif_type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  sender_username?: string | null;
  meta: Record<string, unknown>;
}

interface NotificationState {
  notifications: AppNotification[];
  wsUnreadCount: number;
  isLoading: boolean;
  nextPage: string | null;
  count: number;
}

const initialState: NotificationState = {
  notifications: [],
  wsUnreadCount: 0,
  isLoading: false,
  nextPage: null,
  count: 0,
};

export const fetchNotifications = createAsyncThunk(
  "notifications/fetch",
  async (page: number | undefined, { rejectWithValue }) => {
    try {
      const pageNum = page ?? 1;
      const data = await fetchApi(`/notifications/?page=${pageNum}`);
      return data;
    } catch (err: unknown) {
      if (err instanceof Error) {
        return rejectWithValue(err.message);
      }
      return rejectWithValue("Failed to fetch notifications");
    }
  },
);

export const notificationSlice = createSlice({
  name: "notifications",
  initialState,
  reducers: {
    setWsUnreadCount: (state, action: PayloadAction<number>) => {
      state.wsUnreadCount = action.payload;
    },
    addNotification: (state, action: PayloadAction<AppNotification>) => {
      // Prepend new notification, remove old if duplicated by id
      state.notifications = [
        action.payload,
        ...state.notifications.filter((n) => n.id !== action.payload.id),
      ];
      state.wsUnreadCount += 1;
    },
    markReadLocally: (state, action: PayloadAction<number>) => {
      const notif = state.notifications.find((n) => n.id === action.payload);
      if (notif && !notif.is_read) {
        notif.is_read = true;
      }
      state.wsUnreadCount = Math.max(0, state.wsUnreadCount - 1);
    },
    markAllReadLocally: (state) => {
      state.notifications.forEach((n) => {
        n.is_read = true;
      });
      state.wsUnreadCount = 0;
    },
    setNotifications: (state, action: PayloadAction<AppNotification[]>) => {
      state.notifications = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.isLoading = true;
      })
      .addCase(fetchNotifications.fulfilled, (state, action) => {
        const payload = action.payload as any;
        const page = action.meta.arg ?? 1;

        if (payload && typeof payload === "object" && "results" in payload) {
          const results = payload.results as AppNotification[];
          if (page === 1) {
            state.notifications = results;
          } else {
            const existingIds = new Set(state.notifications.map((n) => n.id));
            const uniqueResults = results.filter((n) => !existingIds.has(n.id));
            state.notifications = [...state.notifications, ...uniqueResults];
          }
          state.nextPage = payload.next;
          state.count = payload.count;
        } else if (Array.isArray(payload)) {
          state.notifications = payload;
          state.nextPage = null;
          state.count = payload.length;
        }
        state.isLoading = false;
      })
      .addCase(fetchNotifications.rejected, (state) => {
        state.isLoading = false;
      });
  },
});

export const {
  setWsUnreadCount,
  addNotification,
  markReadLocally,
  markAllReadLocally,
  setNotifications,
} = notificationSlice.actions;

export default notificationSlice.reducer;
