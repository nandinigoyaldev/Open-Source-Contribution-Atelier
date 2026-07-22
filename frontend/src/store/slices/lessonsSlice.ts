import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface LessonsState {
  lessons: any[];
  loading: boolean;
}

const initialState: LessonsState = {
  lessons: [],
  loading: false,
};

export const lessonsSlice = createSlice({
  name: "lessons",
  initialState,
  reducers: {
    setLessons: (state, action: PayloadAction<any[]>) => {
      state.lessons = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase("RESET_APP_STATE", () => initialState);
  },
});

export const { setLessons, setLoading } = lessonsSlice.actions;
export default lessonsSlice.reducer;
