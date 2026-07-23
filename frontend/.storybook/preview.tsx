import type { Preview } from "@storybook/react-vite";

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },

    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: "todo",
    },

    // Capture Storybook stories at the 3 required viewport widths.
    // Chromatic reads this to run snapshots in each mode on every PR.
    chromatic: {
      modes: {
        mobile: { viewport: { width: 375, height: 812 } },
        tablet: { viewport: { width: 768, height: 1024 } },
        desktop: { viewport: { width: 1280, height: 800 } },
      },
    },
  },
};

export default preview;
