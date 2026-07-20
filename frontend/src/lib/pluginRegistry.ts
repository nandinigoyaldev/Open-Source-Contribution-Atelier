import api from "../api";

export interface PluginManifest {
  name: string;
  display_name: string;
  version: string;
  api_version: string;
  description: string;
  author: string;
  hooks: Record<string, string>;
  views: Record<string, string>;
}

export interface PluginInfo {
  name: string;
  display_name: string;
  version: string;
  api_version: string;
  description: string;
  author: string;
  is_active: boolean;
  manifest: PluginManifest;
}

class PluginRegistry {
  private activePlugins: Map<string, PluginInfo> = new Map();

  async fetchActivePlugins(): Promise<void> {
    try {
      const response = await api.get<PluginInfo[]>("/api/plugins/");
      this.activePlugins.clear();
      response.data.forEach((plugin) => {
        if (plugin.is_active) {
          this.activePlugins.set(plugin.name, plugin);
        }
      });
    } catch (error) {
      console.error("Failed to load active plugins from server:", error);
    }
  }

  isActive(name: string): boolean {
    return this.activePlugins.has(name);
  }

  getPlugin(name: string): PluginInfo | undefined {
    return this.activePlugins.get(name);
  }

  getActivePlugins(): PluginInfo[] {
    return Array.from(this.activePlugins.values());
  }
}

export const pluginRegistry = new PluginRegistry();
