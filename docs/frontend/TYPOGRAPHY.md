# Typography Standardization

We use a clean, modern, and accessible typography system across the Open-Source Contribution Atelier.

## Font Families

- **Inter**: The primary typeface used for all major headings and body content, optimized for screen legibility.
- **Outfit**: Used selectively for stylized or large display elements.
- **JetBrains Mono**: Exclusively for code blocks, terminal outputs, and hash IDs.

## Headings

All `H1`, `H2`, and `H3` tags have been standardized to globally use the **Inter** font family. This is enforced via the global `styles.css` file using Tailwind's `@layer base`:

```css
@layer base {
  h1,
  h2,
  h3 {
    font-family: "Inter", sans-serif;
  }
}
```

### Guidelines for Developers

1. **Avoid Ad-Hoc Overrides**: Do not apply `.font-display`, `.font-mono`, or `.font-sans` classes directly to `<h1>`, `<h2>`, or `<h3>` elements unless specifically rendering code or specialized elements. Let them inherit the base font naturally to preserve the visual hierarchy.
2. **Fallback Strategy**: The `sans-serif` system fallback ensures graceful degradation on slow networks or environments where Google Fonts fails to load.
3. **Weight & Sizing**: Continue using Tailwind utilities like `.font-black`, `.text-4xl`, and `.tracking-tight` on headings to maintain the energetic, vibrant aesthetic of the platform.
