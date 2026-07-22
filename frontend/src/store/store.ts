import { configureStore, combineReducers } from "@reduxjs/toolkit";
import {
  persistStore,
  persistReducer,
  FLUSH,
  REHYDRATE,
  PAUSE,
  PERSIST,
  PURGE,
  REGISTER,
} from "redux-persist";
import storage from "redux-persist/lib/storage";
import authReducer from "../features/auth/authSlice";
import notificationReducer from "../features/notifications/notificationSlice";
import chatReducer from "../components/chat/chatSlice";
import lessonsReducer from "./slices/lessonsSlice";
import challengesReducer from "./slices/challengesSlice";
import progressReducer from "./slices/progressSlice";
import dashboardReducer from "./slices/dashboardSlice";
import { cleanupMiddleware } from "./middleware/cleanupMiddleware";
import { expireIn } from "./persistTransform";

const rootReducer = combineReducers({
  auth: authReducer,
  notifications: notificationReducer,
  chat: chatReducer,
  lessons: lessonsReducer,
  challenges: challengesReducer,
  progress: progressReducer,
  dashboard: dashboardReducer,
});

const persistConfig = {
  key: "root",
  storage,
  blacklist: ["auth"],
  transforms: [
    expireIn(15 * 60 * 1000, "lessons"),
    expireIn(5 * 60 * 1000, "challenges"),
  ],
};

const persistedReducer = persistReducer(persistConfig, rootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
      },
    }).concat(cleanupMiddleware),
  devTools: {
    actionsDenylist: ["persist/REHYDRATE"],
  },
});

export const persistor = persistStore(store);

if (typeof window !== "undefined") {
  (window as any).store = store;
}

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
