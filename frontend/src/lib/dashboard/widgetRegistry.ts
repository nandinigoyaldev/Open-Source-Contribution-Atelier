import { ReactNode } from 'react';

export interface Widget {
  id: string;
  title: string;
  description: string;
  icon: string;
  defaultWidth: number;
  defaultHeight: number;
  component: React.ComponentType<any>;
}

const widgetComponents: Record<string, React.ComponentType<any>> = {};

export function registerWidget(id: string, component: React.ComponentType<any>) {
  widgetComponents[id] = component;
}

export function getWidget(id: string) {
  return widgetComponents[id];
}

// Pre-built widgets
import { StreakCalendar } from '../../components/StreakCalendar';
import { XPBreakdown } from '../../components/XPBreakdown';
import { RecentActivity } from '../../components/RecentActivity';

registerWidget('streak-calendar', StreakCalendar);
registerWidget('xp-breakdown', XPBreakdown);
registerWidget('recent-activity', RecentActivity);