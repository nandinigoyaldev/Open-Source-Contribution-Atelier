/**
 * Notes widget with export functionality.
 * 
 * @file NotesWidget.tsx
 * @location frontend/src/components/Notes/NotesWidget.tsx
 */

import React, { useState, useEffect } from 'react';
import { NotesExportButton } from './NotesExportButton';

// ... existing imports ...

export const NotesWidget: React.FC = () => {
  // ... existing state ...

  return (
    <div className="notes-widget">
      <div className="notes-widget-header">
        <h3 className="text-lg font-semibold text-white">📝 My Notes</h3>
        <div className="flex items-center gap-2">
          {/* ✅ ADD: Export Button */}
          <NotesExportButton size="sm" variant="outline" />
        </div>
      </div>
      
      {/* ... rest of the component ... */}
    </div>
  );
};