import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface ChatMessage {
  id: string;
  text: string;
  sender: string;
  timestamp: number;
}

interface ChatState {
  offlineQueue: ChatMessage[];
  isOnline: boolean;
}

const initialState: ChatState = {
  offlineQueue: [],
  isOnline: navigator.onLine,
};

export const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    enqueueMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.offlineQueue.push(action.payload);
    },
    clearQueue: (state) => {
      state.offlineQueue = [];
    },
    setOnlineStatus: (state, action: PayloadAction<boolean>) => {
      state.isOnline = action.payload;
    },
  },
});

export const { enqueueMessage, clearQueue, setOnlineStatus } =
  chatSlice.actions;
export default chatSlice.reducer;
