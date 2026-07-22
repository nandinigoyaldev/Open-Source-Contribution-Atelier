import { createTransform } from "redux-persist";

export const expireIn = (ttlMs: number, sliceName: string) => {
  return createTransform(
    // transform state on its way to being serialized and persisted.
    (inboundState) => {
      if (!inboundState) return inboundState;
      return {
        ...inboundState,
        _persistedAt: Date.now(),
      };
    },
    // transform state being rehydrated
    (outboundState) => {
      if (!outboundState) return outboundState;
      const { _persistedAt, ...state } = outboundState as any;
      if (typeof _persistedAt === "number" && Date.now() - _persistedAt > ttlMs) {
        // Expired, return undefined to prevent rehydration and fallback to initial state
        return undefined;
      }
      return state;
    },
    { whitelist: [sliceName] }
  );
};
