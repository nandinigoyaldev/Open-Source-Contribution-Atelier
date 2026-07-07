import { createSlice, PayloadAction, createAsyncThunk } from "@reduxjs/toolkit";
import api from "../../api";

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
}

const initialState: NotificationState = {
  notifications: [],
  wsUnreadCount: 0,
  isLoading: false,
};

export const fetchNotifications = createAsyncThunk(
  "notifications/fetch",
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get("/notifications/");
      return res.data as AppNotification[];
    } catch (err: unknown) {
      if (err instanceof Error) {
        return rejectWithValue(err.message);
      }
      return rejectWithValue("Failed to fetch notifications");
    }
  }
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
        state.notifications = action.payload;
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
