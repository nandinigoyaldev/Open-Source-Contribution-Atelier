# RichTextEditor

The `RichTextEditor` component replaces standard `textarea` fields across the platform (such as help requests and user descriptions) with a fully-featured, Markdown-enabled WYSIWYG editing experience.

## Capabilities

It leverages `react-simplemde-editor` (a wrapper around EasyMDE) providing:
- **Rich Formatting:** Headings, Bold, Italic, Blockquotes, Ordered/Unordered Lists.
- **Developer Features:** Inline code and syntax-highlighted code blocks.
- **Link & Tables:** Insert links and structured markdown tables.
- **Split-View / Live Preview:** Users can click the "Preview" or "Side-by-side" icons in the toolbar to verify how their markdown will render.
- **Character Limits:** Seamlessly supports `maxLength`, rendering character counts beneath the editor dynamically.

## Usage Guidelines

Replace any `textarea` managing markdown/text payload logic with `<RichTextEditor />`:

```tsx
import { RichTextEditor } from "../components/ui/RichTextEditor";

// Inside component state
const [description, setDescription] = useState("");

return (
  <RichTextEditor
    id="description-input"
    placeholder="Write your issue description here..."
    value={description}
    onChange={setDescription}
    maxLength={1000} // Optional
    disabled={isSubmitting} // Optional
  />
);
```

## Styling & Brutalist Design
The editor is heavily customized in `src/styles.css` using Tailwind and raw CSS overrides to match the platform's brutalist aesthetics.
- The `editor-toolbar` has a thick 4px black border and sharp edges.
- The `CodeMirror` active input field has been restyled to utilize the `JetBrains Mono` font for a more developer-focused writing feel.
- Dark mode compatibility is natively integrated via `html.dark` pseudo-selectors in the stylesheet.

## Extension Points
To add custom buttons, shortcuts, or modify toolbar actions, edit the `options` object inside `frontend/src/components/ui/RichTextEditor.tsx`.

```tsx
toolbar: [
  "bold", "italic", "heading", "|",
  // ... add custom actions like custom image uploaders here ...
  "guide"
]
```
