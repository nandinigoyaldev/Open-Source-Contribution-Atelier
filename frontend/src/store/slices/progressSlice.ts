import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface ProgressState {
  progress: Record<string, any>;
  loading: boolean;
}

const initialState: ProgressState = {
  progress: {},
  loading: false,
};

export const progressSlice = createSlice({
  name: "progress",
  initialState,
  reducers: {
    setProgress: (state, action: PayloadAction<Record<string, any>>) => {
      state.progress = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase("RESET_APP_STATE", () => initialState);
  },
});

export const { setProgress, setLoading } = progressSlice.actions;
export default progressSlice.reducer;
