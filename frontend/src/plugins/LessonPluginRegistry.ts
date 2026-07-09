import React from 'react';
import { Lesson } from '../lib/lessons';

export interface LessonPlugin {
  /** Unique identifier for the plugin (e.g. 'python_sandbox', 'quiz') */
  type: string;
  
  /** Metadata version to handle compatibility */
  version: string;
  
  /** Determines if this plugin can render the given lesson data */
  canHandle: (lesson: Lesson) => boolean;
  
  /** The React component used to render the interactive portion of the lesson */
  component: React.ComponentType<{ 
    lesson: Lesson;
    onSuccess: (score?: number) => void;
  }>;
}

class PluginRegistry {
  private plugins = new Map<string, LessonPlugin>();

  register(plugin: LessonPlugin) {
    if (!plugin.type) {
      console.error("Plugin failed to register: missing 'type'");
      return;
    }
    this.plugins.set(plugin.type, plugin);
    console.log(`[PluginRegistry] Registered frontend plugin: ${plugin.type} v${plugin.version}`);
  }

  getPluginForLesson(lesson: Lesson): LessonPlugin | null {
    // Strategy: First plugin that claims it can handle the lesson wins.
    for (const plugin of this.plugins.values()) {
      try {
        if (plugin.canHandle(lesson)) {
          return plugin;
        }
      } catch (err) {
        console.error(`Error checking plugin ${plugin.type}:`, err);
      }
    }
    return null;
  }

  getAllPlugins(): LessonPlugin[] {
    return Array.from(this.plugins.values());
  }
}

export const lessonPluginRegistry = new PluginRegistry();
