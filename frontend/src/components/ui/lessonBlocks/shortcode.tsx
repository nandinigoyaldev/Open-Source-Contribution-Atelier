import React from "react";
import { pluginRegistry } from "../../../lib/markdownPlugins";
import type { LessonBlockHandler } from "./types";

/**
 * Interactive components embedded as `[name key="value"]` on a line of their own. The components
 * themselves are registered in `lib/markdownPlugins.ts`; an unknown name shows an inline message
 * instead of being dropped.
 */
export const shortcodeBlock: LessonBlockHandler = {
  id: "shortcode",
  priority: 1000,
  render: ({ line, index }) => {
    const match = line.trim().match(/^\[([a-zA-Z0-9-]+)(?:\s+(.*?))?\]$/);
    if (!match || line.includes("](")) return null;

    const pluginName = match[1];
    const propsString = match[2] || "";

    const PluginComponent = pluginRegistry[pluginName];
    if (!PluginComponent) {
      return {
        node: (
          <div className="p-4 my-4 bg-red-50 border-4 border-red-500 rounded-xl text-red-700 font-bold shadow-card-sm">
            Unsupported interactive component: {pluginName}
          </div>
        ),
        next: index + 1,
      };
    }

    // Parse props like key="value"
    const props: Record<string, string> = {};
    const propRegex = /([a-zA-Z0-9-]+)="([^"]*)"/g;
    let propMatch;
    while ((propMatch = propRegex.exec(propsString)) !== null) {
      props[propMatch[1]] = propMatch[2];
    }

    return {
      node: (
        <div className="my-4">
          <PluginComponent {...props} />
        </div>
      ),
      next: index + 1,
    };
  },
};
