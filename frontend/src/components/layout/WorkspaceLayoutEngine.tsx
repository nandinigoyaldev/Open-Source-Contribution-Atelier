import React, { useEffect, useState } from 'react';
import { Layout, Model, TabNode, IJsonModel, Action } from 'flexlayout-react';
import 'flexlayout-react/style/dark.css';
import { Save, LayoutTemplate, RotateCcw } from 'lucide-react';

const DEFAULT_LAYOUT: IJsonModel = {
  global: {
    tabEnableClose: true,
    tabEnableRename: false,
    tabSetEnableMaximize: true,
  },
  borders: [
    {
      type: 'border',
      location: 'left',
      size: 250,
      children: [
        {
          type: 'tab',
          name: 'Explorer',
          component: 'explorer',
          enableClose: false,
        }
      ]
    },
    {
      type: 'border',
      location: 'bottom',
      size: 200,
      children: [
        {
          type: 'tab',
          name: 'Console',
          component: 'console',
          enableClose: false,
        }
      ]
    }
  ],
  layout: {
    type: 'row',
    weight: 100,
    children: [
      {
        type: 'tabset',
        weight: 100,
        id: 'editor-area',
        children: [
          {
            type: 'tab',
            name: 'Welcome',
            component: 'editor',
            id: 'welcome-tab'
          }
        ]
      }
    ]
  }
};

interface WorkspaceLayoutEngineProps {
  explorerContent: React.ReactNode;
  editorContent: (tabId: string) => React.ReactNode;
  consoleContent: React.ReactNode;
  onLayoutChange?: (model: IJsonModel) => void;
  savedLayout?: IJsonModel;
  onSaveLayout?: (model: IJsonModel) => void;
}

export function WorkspaceLayoutEngine({
  explorerContent,
  editorContent,
  consoleContent,
  onLayoutChange,
  savedLayout,
  onSaveLayout
}: WorkspaceLayoutEngineProps) {
  const [model, setModel] = useState<Model>(() => {
    try {
      if (savedLayout && Object.keys(savedLayout).length > 0) {
        return Model.fromJson(savedLayout);
      }
      return Model.fromJson(DEFAULT_LAYOUT);
    } catch (e) {
      console.error("Failed to parse saved layout, falling back to default", e);
      return Model.fromJson(DEFAULT_LAYOUT);
    }
  });
  
  // Re-initialize model if savedLayout prop changes and is valid
  useEffect(() => {
    if (savedLayout && Object.keys(savedLayout).length > 0) {
      try {
        setModel(Model.fromJson(savedLayout));
      } catch (e) {
        console.error("Failed to parse saved layout", e);
      }
    }
  }, [savedLayout]);

  const factory = (node: TabNode) => {
    const component = node.getComponent();
    if (component === 'explorer') {
      return <div className="h-full w-full overflow-hidden bg-[#1e1e1e] text-gray-300">{explorerContent}</div>;
    }
    if (component === 'console') {
      return <div className="h-full w-full overflow-hidden bg-[#151411] text-gray-300">{consoleContent}</div>;
    }
    if (component === 'editor') {
      return <div className="h-full w-full bg-[#1e1e1e]">{editorContent(node.getId())}</div>;
    }
    return <div>Component not found</div>;
  };

  const handleModelChange = (action: Action) => {
    if (onLayoutChange) {
      onLayoutChange(model.toJson());
    }
    return action;
  };

  const resetLayout = () => {
    setModel(Model.fromJson(DEFAULT_LAYOUT));
    if (onLayoutChange) onLayoutChange(DEFAULT_LAYOUT);
  };

  return (
    <div className="flex flex-col h-full w-full bg-[#252525]">
      {/* Layout Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-[#1e1e1e]">
        <div className="flex items-center gap-2">
          <LayoutTemplate className="w-4 h-4 text-gray-400" />
          <span className="text-xs font-semibold text-gray-400">Workspace Layout</span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={resetLayout}
            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="Reset to Default Layout"
          >
            <RotateCcw className="w-3 h-3" /> Reset
          </button>
          <button 
            onClick={() => onSaveLayout && onSaveLayout(model.toJson())}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
          >
            <Save className="w-3 h-3" /> Save Layout
          </button>
        </div>
      </div>
      
      {/* Layout Area */}
      <div className="flex-1 relative">
        <Layout 
          model={model} 
          factory={factory} 
          onAction={handleModelChange}
        />
      </div>
    </div>
  );
}
