/**
 * useNetworkStatus.ts
 * Convenience hook to access the NetworkStatusContext value.
 */
import { useContext } from "react";
import { NetworkStatusContext, NetworkStatusContextValue } from "./NetworkStatusContext";

export function useNetworkStatus(): NetworkStatusContextValue {
  return useContext(NetworkStatusContext);
}
