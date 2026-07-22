import { Middleware } from "@reduxjs/toolkit";

export const cleanupMiddleware: Middleware = (store) => (next) => (action: any) => {
  if (action && action.type === "LOCATION_CHANGE") {
    // Dispatch RESET_APP_STATE when location changes to trigger page-level slice cleanup
    store.dispatch({ type: "RESET_APP_STATE", payload: action.payload });
  }
  return next(action);
};
