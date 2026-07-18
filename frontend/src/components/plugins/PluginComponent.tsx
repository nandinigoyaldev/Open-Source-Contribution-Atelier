import React, { lazy, Suspense, useEffect, useState } from "react";
import { pluginRegistry } from "../../lib/pluginRegistry";

// Static mapping of plugin components for Vite build compatibility
const componentMap: Record<string, Record<string, React.ComponentType<any>>> = {
  github_stats: {
    StatsWidget: lazy(() => import("./github_stats/StatsWidget")),
  },
};

interface PluginComponentProps {
  pluginName: string;
  componentName: string;
  props?: any;
  fallback?: React.ReactNode;
}

export function PluginComponent({
  pluginName,
  componentName,
  props = {},
  fallback = <div className="animate-pulse bg-gray-100 dark:bg-gray-800 h-10 w-full rounded-md" />,
}: PluginComponentProps) {
  const [isActive, setIsActive] = useState(false);

  useEffect(() => {
    // Check if plugin is active in registry
    setIsActive(pluginRegistry.isActive(pluginName));
  }, [pluginName]);

  if (!isActive) return null;

  const PluginComp = componentMap[pluginName]?.[componentName];
  if (!PluginComp) {
    console.warn(`Plugin component ${pluginName}/${componentName} not found in client mapping.`);
    return null;
  }

  return (
    <Suspense fallback={fallback}>
      <PluginComp {...props} />
    </Suspense>
  );
}
