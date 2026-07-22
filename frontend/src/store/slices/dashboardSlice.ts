import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface DashboardState {
  widgets: any[];
  loading: boolean;
}

const initialState: DashboardState = {
  widgets: [],
  loading: false,
};

export const dashboardSlice = createSlice({
  name: "dashboard",
  initialState,
  reducers: {
    setWidgets: (state, action: PayloadAction<any[]>) => {
      state.widgets = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase("RESET_APP_STATE", () => initialState);
  },
});

export const { setWidgets, setLoading } = dashboardSlice.actions;
export default dashboardSlice.reducer;
