import React, { useState, useEffect } from "react";
import { MentionsInput, Mention, SuggestionDataItem } from "react-mentions";
import { fetchApi } from "../../lib/api";

interface MentionTextareaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  rows?: number;
  required?: boolean;
}

export function MentionTextarea({
  value,
  onChange,
  placeholder,
  className,
  rows = 4,
  required = false,
}: MentionTextareaProps) {
  const fetchUsers = async (
    query: string,
    callback: (data: SuggestionDataItem[]) => void,
  ) => {
    if (!query) {
      callback([]);
      return;
    }

    try {
      const results = await fetchApi(`/accounts/users/suggestions/?q=${query}`);
      const suggestions = results.map((user: any) => ({
        id: user.username,
        display: user.username,
        avatar_url: user.avatar_url,
      }));
      callback(suggestions);
    } catch (error) {
      console.error("Failed to fetch user suggestions", error);
      callback([]);
    }
  };

  const defaultStyle = {
    control: {
      backgroundColor: "transparent",
      fontSize: 14,
      fontWeight: "normal",
    },
    input: {
      padding: "0.5rem 1rem",
      margin: 0,
    },
    suggestions: {
      list: {
        backgroundColor: "white",
        border: "1px solid rgba(0,0,0,0.15)",
        fontSize: 14,
        borderRadius: "0.5rem",
        overflow: "hidden",
        boxShadow:
          "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
      },
      item: {
        padding: "5px 15px",
        borderBottom: "1px solid rgba(0,0,0,0.05)",
        "&focused": {
          backgroundColor: "#eff6ff",
        },
      },
    },
  };

  return (
    <div className={`relative ${className || ""}`}>
      <style
        dangerouslySetInnerHTML={{
          __html: `
        .mention-textarea textarea {
          min-height: ${rows * 24}px;
          border-radius: 0.5rem;
          border: 2px solid black;
          padding: 0.5rem 1rem;
          width: 100%;
        }
        .mention-textarea textarea:focus {
          outline: none;
          ring: 2px;
          border-color: #3b82f6; /* primary or distinct color */
        }
        .mention-highlight {
          background-color: #dbeafe;
          border-radius: 0.25rem;
          padding: 0 0.125rem;
          color: #1d4ed8;
          font-weight: 600;
        }
      `,
        }}
      />
      <MentionsInput
        value={value}
        onChange={(e: { target: { value: string } }, newValue: string) => onChange(newValue)}
        style={defaultStyle}
        className="mention-textarea font-mono text-sm dark:bg-black dark:border-[#2e2924]"
        placeholder={placeholder}
        a11ySuggestionsListLabel={"Suggested users"}
        allowSpaceInQuery={false}
      >
        <Mention
          trigger="@"
          data={fetchUsers}
          markup="@__display__"
          displayTransform={(id: string | number, display: string) => `@${display}`}
          className="mention-highlight z-10"
          renderSuggestion={(
  suggestion: SuggestionDataItem,
  search: string,
  highlightedDisplay: React.ReactNode,
  index: number,
  focused: boolean
) => (
            <div
              className={`flex items-center gap-2 ${focused ? "bg-blue-50 text-blue-900" : "bg-white text-black"} dark:bg-[#1a1816] dark:text-white p-2 transition-colors`}
            >
              <div className="w-6 h-6 rounded-full bg-gray-200 overflow-hidden shrink-0 border border-gray-300">
                {(suggestion as any).avatar_url ? (
                  <img
                    src={(suggestion as any).avatar_url}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-gray-500 font-bold">
                    {(suggestion.display || suggestion.id || "?")
                      .toString()[0]
                      .toUpperCase()}
                  </div>
                )}
              </div>
              <span className="font-bold">
                {suggestion.display || suggestion.id}
              </span>
            </div>
          )}
        />
      </MentionsInput>
    </div>
  );
}
