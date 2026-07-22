import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface ChallengesState {
  challenges: any[];
  loading: boolean;
}

const initialState: ChallengesState = {
  challenges: [],
  loading: false,
};

export const challengesSlice = createSlice({
  name: "challenges",
  initialState,
  reducers: {
    setChallenges: (state, action: PayloadAction<any[]>) => {
      state.challenges = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase("RESET_APP_STATE", () => initialState);
  },
});

export const { setChallenges, setLoading } = challengesSlice.actions;
export default challengesSlice.reducer;
