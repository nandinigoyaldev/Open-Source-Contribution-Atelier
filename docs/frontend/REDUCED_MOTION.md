# Reduced motion in progress and celebration UI

The app honors the operating system's `prefers-reduced-motion: reduce` preference. In `frontend/src/index.css`, CSS animations and transitions complete immediately while their final content and status remain visible. This covers progress indicators, badge celebrations, loading shimmer, and other CSS/Tailwind motion without hiding success or error messages.

For JavaScript animation, CSS alone is insufficient: Framer Motion changes inline styles frame by frame. Use `useReducedMotion()` from `framer-motion` and keep the final state visible. For example, a progress fill can use `initial={reduceMotion ? false : { width: 0 }}`, `animate={{ width: progressWidth }}`, and a zero-duration transition when reduction is requested. Avoid looping scale, rotation, or bouncing keyframes in reduced mode. `StreakWidget`, `XPBadgeCalculator`, and `BadgesCabinet` show this pattern.

For a new component, test both preferences. With reduced motion enabled, changing progress or unlocking a badge must still update the number, label, and final visual state immediately. Do not use motion as the only indication that a state changed. Check the rendered control with keyboard and screen-reader navigation as well as a browser or component test.
