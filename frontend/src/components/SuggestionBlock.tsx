import React, { useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

interface SuggestionBlockProps {
  suggestion: {
    id: string;
    file_path: string;
    line_start: number;
    line_end: number;
    original_code: string;
    suggested_code: string;
    status: string;
  };
  onAccept: (id: string) => void;
  onReject: (id: string, reason: string) => void;
}

export function SuggestionBlock({ suggestion, onAccept, onReject }: SuggestionBlockProps) {
  const [reason, setReason] = useState('');
  const [showReason, setShowReason] = useState(false);

  if (suggestion.status === 'accepted') {
    return <div className="suggestion-accepted">✅ Suggestion accepted</div>;
  }

  if (suggestion.status === 'rejected') {
    return <div className="suggestion-rejected">❌ Suggestion rejected</div>;
  }

  return (
    <div className="suggestion-block">
      <div className="suggestion-header">
        <span className="suggestion-file">{suggestion.file_path}</span>
        <span className="suggestion-lines">Lines {suggestion.line_start}-{suggestion.line_end}</span>
      </div>

      <div className="diff-view">
        <div className="diff-removed">
          <span className="diff-label">-</span>
          <pre>{suggestion.original_code}</pre>
        </div>
        <div className="diff-added">
          <span className="diff-label">+</span>
          <pre>{suggestion.suggested_code}</pre>
        </div>
      </div>

      <div className="suggestion-actions">
        <button 
          className="btn-accept"
          onClick={() => onAccept(suggestion.id)}
        >
          ✅ Accept
        </button>
        
        <button 
          className="btn-reject"
          onClick={() => setShowReason(true)}
        >
          ❌ Reject
        </button>

        {showReason && (
          <div className="reject-reason">
            <input
              type="text"
              placeholder="Reason for rejection..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <button onClick={() => onReject(suggestion.id, reason)}>
              Submit
            </button>
            <button onClick={() => setShowReason(false)}>Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}