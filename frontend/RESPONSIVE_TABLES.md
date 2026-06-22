# Responsive Table System

We use a unified `ResponsiveTable` component for rendering grid-based data. It dynamically restructures itself based on device viewport sizes to maintain usability without sacrificing information.

## Layout Behaviors

### Desktop Layout (`>= 640px`)
- Renders as a standard HTML `<table>`.
- Nested inside a horizontally scrollable container (`overflow-x-auto`) to ensure exceptionally wide rows or many columns don't break the layout.
- Provides standard table semantics for screen readers.

### Mobile Layout (`< 640px`)
- Renders as a vertical stack of "Cards".
- Each card represents a single data row.
- Each property inside the card explicitly declares the column's `label` on the left, and the `value` on the right (flexbox layout) to ensure context isn't lost.

## Usage Guide

```tsx
import { ResponsiveTable } from "../components/ui/ResponsiveTable";

// ... inside component
<ResponsiveTable
  data={userList}
  keyExtractor={(item) => item.id.toString()}
  emptyMessage="No users found."
  columns={[
    {
      header: "Rank",
      accessor: "rank",
      label: "User Rank" // Optional: Overrides header for mobile view
    },
    {
      header: "Actions",
      accessor: (item, idx) => (
         <button onClick={() => delete(item.id)}>Delete</button>
      )
    }
  ]}
/>
```

### Component Guidelines
- **Always use `ResponsiveTable`** instead of raw `<table>` implementations for user-data lists. Raw tables break easily on constrained mobile environments.
- **Provide clear `label` values**: If a column `header` is complex (like an icon), you MUST provide a plain string `label` for the mobile card layout so it can properly align the value.
