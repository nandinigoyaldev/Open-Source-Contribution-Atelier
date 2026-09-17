# Scroll To Top Utility

To enhance navigation on long pages such as lessons, community leaderboards, and dashboard sections, the application includes a responsive `ScrollToTop` action component.

## Behavior

- **Visibility Threshold**: The button remains hidden when near the top of the page. It automatically fades into view once the window scroll position exceeds `300px`.
- **Smooth Scroll**: When clicked, the viewport uses `behavior: "smooth"` to animate the scroll position back to `top: 0` to avoid abrupt disorienting jumps.
- **Accessibility**: It is properly labeled for screen readers (`aria-label="Scroll to top"`) and features a high-contrast focus ring indicating keyboard focus.

## Usage

The `ScrollToTop` component operates completely independently using native Window APIs.

**Global Integration:**
It has already been implemented globally inside `AppLayout.tsx`. It lives outside the `<main>` structural routes, meaning it automatically works on every page across the entire application without any further configuration.

```tsx
// frontend/src/components/layout/AppLayout.tsx
import { ScrollToTop } from "../ui/ScrollToTop";

export function AppLayout() {
  return (
    <div className="min-h-screen">
      <Navigation />
      <main>
        <Outlet />
      </main>
      <ScrollToTop /> {/* Globally integrated here */}
    </div>
  );
}
```

If you ever need to disable it on a specific route or build a specific modal component that handles its own scrolling context instead of the global `window`, you may extract it from `AppLayout` or configure conditional rendering.

## Testing

Comprehensive unit tests mapping out scroll boundary thresholds and DOM visibility assertion have been added to `frontend/src/test/ScrollToTop.test.tsx`.
