# Lesson block registry

Lesson markdown is rendered by `MarkdownRenderer` (`frontend/src/components/ui/MarkdownRenderer.tsx`).
It used to hold one long chain of `if` statements, one per kind of block. Each kind is now a small
handler in `frontend/src/components/ui/lessonBlocks/`, and the renderer only asks the registry who
owns each line. Adding a new curriculum block type means registering one handler; nothing in the
renderer changes.

## What the renderer still does

* **Sanitization.** The whole source goes through DOMPurify (same allow-list as before) before any
  handler sees it. Handlers receive sanitized lines. Link and image URLs are additionally checked
  with `safeLinkHref` / `safeImageSrc` (`lessonBlocks/safeUrl.ts`).
* **Inline markdown and the glossary.** Bold, inline code, links and glossary terms are handled by
  `parseInline`, which is passed to every handler. Use it for any user text.
* **Order.** The built-in blocks are tried in the order they always were.

## A handler

```tsx
import { lessonBlockRegistry } from "components/ui/lessonBlocks";

lessonBlockRegistry.register({
  id: "video",
  priority: 950, // optional, see below
  render: ({ lines, line, index, parseInline }) => {
    const m = line.trim().match(/^::video\[(.+?)\]\s*(.*)$/);
    if (!m) return null; // not mine: the next handler is asked
    return {
      node: (
        <figure>
          <video src={m[1]} controls />
          <figcaption>{parseInline(m[2])}</figcaption>
        </figure>
      ),
      next: index + 1, // first line after the block
    };
  },
});
```

* Return `null` if the line at `index` is not yours. A block may take several lines (read
  `lines[index + 1 ...]`); `next` is the index to continue from and must be greater than `index`.
* Registering an id again replaces that handler. `register` returns a function that removes it.
* `priority`: handlers are tried lowest number first, ties in registration order. Built-ins use
  100–1200 (blank line, code fence, heading, rule, alert, blockquote, table, bullet list, numbered
  list, shortcode, HTML image, markdown image) and the paragraph fallback uses 10000. The default,
  1500, runs after all built-ins except the paragraph, which suits syntax that no built-in block
  would claim. If your syntax starts like a built-in one (`>`, `-`, `|`, a fence), pick a number
  below that block's.
* For tests or a preview with its own set of blocks, pass `registry={createDefaultLessonBlockRegistry()}`
  (plus your handlers) to `MarkdownRenderer`.

## Interactive components

`[name key="value"]` on a line of its own is handled by the `shortcode` block, which looks the
name up in `lib/markdownPlugins.ts`. An unknown name shows "Unsupported interactive component".
That is unchanged.

## Errors

A broken block does not take the lesson down.

* A handler that throws, returns a `next` that does not move forward, or a line that no handler
  accepts, shows "This part of the lesson could not be displayed." in that place (`role="alert"`),
  is logged with the handler's id and the original message, and rendering continues with the next
  line.
* A component inside a block that throws while rendering is caught by a per-block error boundary
  (`BlockBoundary`), shown the same way and reported to Sentry. The block is tried again when its
  source text changes, so a live preview recovers as soon as the text is fixed.
* The message shown to learners carries no technical detail.

## Tests

`frontend/src/components/ui/lessonBlocks/lessonBlocks.test.tsx` covers the registry (ordering,
replacement, validation, forward progress), the built-in order, rendering of every built-in block,
sanitization, adding a block (single and multi-line, overriding a built-in, glossary through
`parseInline`) and the error paths.
