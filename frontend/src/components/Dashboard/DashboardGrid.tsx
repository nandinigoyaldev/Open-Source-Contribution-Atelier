import React, { useState, useEffect } from "react";
import { Rnd } from "react-rnd";
import { fetchApi } from "../../lib/api";

interface Widget {
  id: string;
  widget_type: string;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  visible: boolean;
}

export function DashboardGrid() {
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLayout();
  }, []);

  const fetchLayout = async () => {
    try {
      const data = await fetchApi("/dashboard/layout/");
      setWidgets(data.widgets);
    } catch (error) {
      console.error("Failed to load dashboard:", error);
    } finally {
      setLoading(false);
    }
  };

  const onDragStop = async (id: string, x: number, y: number) => {
    const updated = widgets.map((w) =>
      w.id === id ? { ...w, position_x: x, position_y: y } : w,
    );
    setWidgets(updated);
    saveLayout(updated);
  };

  const onResize = async (id: string, width: number, height: number) => {
    const updated = widgets.map((w) =>
      w.id === id ? { ...w, width, height } : w,
    );
    setWidgets(updated);
    saveLayout(updated);
  };

  const saveLayout = async (updatedWidgets: Widget[]) => {
    await fetchApi("/dashboard/layout/", {
      method: "POST",
      body: JSON.stringify({ widgets: updatedWidgets }),
    });
  };

  if (loading) return <div>Loading dashboard...</div>;

  return (
    <div className="dashboard-grid">
      {widgets.map((widget) => (
        <Rnd
          key={widget.id}
          default={{
            x: widget.position_x * 100,
            y: widget.position_y * 100,
            width: widget.width * 100,
            height: widget.height * 100,
          }}
          onDragStop={(_e: any, d: { x: number; y: number }) => {
            onDragStop(widget.id, d.x / 100, d.y / 100);
          }}
          onResizeStop={(
            _e: any,
            _dir: any,
            ref: { offsetWidth: number; offsetHeight: number },
          ) => {
            onResize(widget.id, ref.offsetWidth / 100, ref.offsetHeight / 100);
          }}
        >
          <div className="widget-container">
            <div className="widget-header">
              <span className="widget-title">{widget.widget_type}</span>
            </div>
            <div className="widget-content">{/* Widget content */}</div>
          </div>
        </Rnd>
      ))}
    </div>
  );
}
