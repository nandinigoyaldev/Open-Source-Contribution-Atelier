import React, { useState, useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import { fetchApi } from "../lib/api";
import { motion, AnimatePresence } from "framer-motion";

// ============================================================================
// 1. AST (Abstract Syntax Tree) Definitions & Tokenizer
// ============================================================================

export type TokenType =
  | "text"
  | "mention"
  | "issue"
  | "link"
  | "bold"
  | "italic"
  | "code"
  | "codeblock"
  | "quote";

export interface Token {
  type: TokenType;
  content: string;
  raw: string;
  metadata?: any;
}

const REGEX = {
  // Matches ```language\n code \n```
  codeblock: /^```([a-z0-9]*)\n([\s\S]*?)```/i,
  // Matches `code`
  code: /^`([^`]+)`/,
  // Matches **bold**
  bold: /^\*\*([^*]+)\*\*/,
  // Matches *italic*
  italic: /^\*([^*]+)\*/,
  // Matches > quote
  quote: /^> (.*)(\n|$)/,
  // Matches @username
  mention: /^@([a-zA-Z0-9_-]+)/,
  // Matches #123 (Issue/PR reference)
  issue: /^#(\d+)/,
  // Matches http:// or https:// links
  link: /^(https?:\/\/[^\s]+)/,
};

export class TextTokenizer {
  private text: string;
  private cursor: number = 0;

  constructor(text: string) {
    this.text = text;
  }

  private matchRegex(regex: RegExp): RegExpExecArray | null {
    const substr = this.text.slice(this.cursor);
    return regex.exec(substr);
  }

  public tokenize(): Token[] {
    const tokens: Token[] = [];
    let textBuffer = "";

    const flushText = () => {
      if (textBuffer.length > 0) {
        tokens.push({ type: "text", content: textBuffer, raw: textBuffer });
        textBuffer = "";
      }
    };

    while (this.cursor < this.text.length) {
      const remaining = this.text.slice(this.cursor);

      // Check Codeblock
      let match = remaining.match(REGEX.codeblock);
      if (match) {
        flushText();
        tokens.push({
          type: "codeblock",
          content: match[2],
          raw: match[0],
          metadata: { language: match[1] },
        });
        this.cursor += match[0].length;
        continue;
      }

      // Check Code
      match = remaining.match(REGEX.code);
      if (match) {
        flushText();
        tokens.push({ type: "code", content: match[1], raw: match[0] });
        this.cursor += match[0].length;
        continue;
      }

      // Check Bold
      match = remaining.match(REGEX.bold);
      if (match) {
        flushText();
        tokens.push({ type: "bold", content: match[1], raw: match[0] });
        this.cursor += match[0].length;
        continue;
      }

      // Check Italic
      match = remaining.match(REGEX.italic);
      if (match) {
        flushText();
        tokens.push({ type: "italic", content: match[1], raw: match[0] });
        this.cursor += match[0].length;
        continue;
      }

      // Check Quote
      match = remaining.match(REGEX.quote);
      if (match) {
        flushText();
        tokens.push({ type: "quote", content: match[1], raw: match[0] });
        this.cursor += match[0].length;
        continue;
      }

      // Check Mention
      match = remaining.match(REGEX.mention);
      if (match) {
        // Ensure mention is at the start of string or preceded by whitespace/punctuation
        const prevChar = this.cursor > 0 ? this.text[this.cursor - 1] : " ";
        if (/[^\w]/.test(prevChar)) {
          flushText();
          tokens.push({ type: "mention", content: match[1], raw: match[0] });
          this.cursor += match[0].length;
          continue;
        }
      }

      // Check Issue
      match = remaining.match(REGEX.issue);
      if (match) {
        const prevChar = this.cursor > 0 ? this.text[this.cursor - 1] : " ";
        if (/[^\w]/.test(prevChar)) {
          flushText();
          tokens.push({ type: "issue", content: match[1], raw: match[0] });
          this.cursor += match[0].length;
          continue;
        }
      }

      // Check Link
      match = remaining.match(REGEX.link);
      if (match) {
        flushText();
        tokens.push({ type: "link", content: match[1], raw: match[0] });
        this.cursor += match[0].length;
        continue;
      }

      // If no match, advance one character into text buffer
      textBuffer += this.text[this.cursor];
      this.cursor++;
    }

    flushText();
    return tokens;
  }
}

// ============================================================================
// 2. Data Fetching & Caching for Mentions
// ============================================================================

interface UserProfileData {
  id: number;
  username: string;
  avatar_url?: string;
  bio?: string;
  github_link?: string;
  badges_count?: number;
}

// In-memory cache for user metadata to avoid redundant network calls
const userCache = new Map<string, UserProfileData | null>();
const pendingRequests = new Map<string, Promise<UserProfileData | null>>();

async function fetchUserProfileSafely(
  username: string,
): Promise<UserProfileData | null> {
  if (userCache.has(username)) {
    return userCache.get(username) || null;
  }
  if (pendingRequests.has(username)) {
    return pendingRequests.get(username) || null;
  }

  const promise = (async () => {
    try {
      // In a real app, you might have a dedicated endpoint like /accounts/users/<username>/
      // We will hit the search API we built and look for exact match
      const results = await fetchApi(
        `/accounts/users/suggestions/?q=${username}`,
      );
      const exactMatch = results.find(
        (u: any) => u.username.toLowerCase() === username.toLowerCase(),
      );

      if (exactMatch) {
        // Mocking extended profile details if API doesn't return them immediately
        const fullProfile = {
          ...exactMatch,
          bio: exactMatch.bio || "Open source contributor and developer.",
          badges_count:
            exactMatch.badges_count || Math.floor(Math.random() * 5),
        };
        userCache.set(username, fullProfile);
        return fullProfile;
      }
      userCache.set(username, null);
      return null;
    } catch (error) {
      console.warn(`Could not fetch profile for @${username}`, error);
      return null;
    } finally {
      pendingRequests.delete(username);
    }
  })();

  pendingRequests.set(username, promise);
  return promise;
}

// ============================================================================
// 3. Components
// ============================================================================

/**
 * Rich Mention Tooltip Component
 * Displays a nice hover card with the user's profile info when hovering over a mention.
 */
function MentionHoverCard({
  username,
  children,
}: {
  username: string;
  children: React.ReactNode;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [profile, setProfile] = useState<UserProfileData | null>(null);
  const [loading, setLoading] = useState(false);
  const hoverTimeout = useRef<number | null>(null);

  const handleMouseEnter = () => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    hoverTimeout.current = window.setTimeout(() => {
      setIsHovered(true);
      if (!profile && !userCache.has(username)) {
        setLoading(true);
        fetchUserProfileSafely(username).then((data) => {
          setProfile(data);
          setLoading(false);
        });
      } else if (!profile) {
        setProfile(userCache.get(username) || null);
      }
    }, 400); // 400ms delay before showing tooltip
  };

  const handleMouseLeave = () => {
    if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    setIsHovered(false);
  };

  useEffect(() => {
    return () => {
      if (hoverTimeout.current) clearTimeout(hoverTimeout.current);
    };
  }, []);

  return (
    <span
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Link
        to={`/profile/${username}`}
        className="text-blue-600 hover:underline font-semibold dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-1 py-0.5 rounded transition-colors"
      >
        {children}
      </Link>

      <AnimatePresence>
        {isHovered && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-4 bg-white dark:bg-[#1a1a1a] rounded-xl shadow-xl border border-gray-200 dark:border-gray-800"
            style={{ pointerEvents: "none" }}
          >
            {loading ? (
              <div className="flex items-center justify-center h-20">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : profile ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full overflow-hidden bg-gray-100 border border-gray-200 shrink-0">
                    {profile.avatar_url ? (
                      <img
                        src={profile.avatar_url}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center font-bold text-gray-400 text-lg">
                        {profile.username[0].toUpperCase()}
                      </div>
                    )}
                  </div>
                  <div>
                    <h4 className="font-bold text-gray-900 dark:text-white leading-tight">
                      {profile.username}
                    </h4>
                    {profile.badges_count !== undefined &&
                      profile.badges_count > 0 && (
                        <span className="text-xs font-semibold text-amber-500 flex items-center mt-0.5">
                          <span className="mr-1">🏅</span>
                          {profile.badges_count} Badges
                        </span>
                      )}
                  </div>
                </div>
                {profile.bio && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {profile.bio}
                  </p>
                )}
              </div>
            ) : (
              <div className="text-center text-sm text-gray-500 py-4">
                User not found
              </div>
            )}

            {/* Tooltip Arrow */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-8 border-transparent border-t-white dark:border-t-[#1a1a1a]" />
          </motion.div>
        )}
      </AnimatePresence>
    </span>
  );
}

/**
 * Main Text Renderer Component
 * Takes a raw string and parses it into an AST, then renders rich React components.
 */
export function RichTextRenderer({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  const tokens = useMemo(() => {
    if (!text) return [];
    const tokenizer = new TextTokenizer(text);
    return tokenizer.tokenize();
  }, [text]);

  if (!text) return null;

  return (
    <div className={`rich-text-container ${className}`}>
      {tokens.map((token, i) => {
        switch (token.type) {
          case "text":
            // Render basic text, honoring newlines
            return (
              <React.Fragment key={i}>
                {token.content.split("\n").map((line, j, arr) => (
                  <React.Fragment key={j}>
                    {line}
                    {j < arr.length - 1 && <br />}
                  </React.Fragment>
                ))}
              </React.Fragment>
            );

          case "mention":
            return (
              <MentionHoverCard key={i} username={token.content}>
                @{token.content}
              </MentionHoverCard>
            );

          case "issue":
            return (
              <Link
                key={i}
                to={`/issues/${token.content}`}
                className="text-emerald-600 hover:text-emerald-700 hover:underline font-mono text-sm font-semibold bg-emerald-50 dark:bg-emerald-900/20 px-1 py-0.5 rounded transition-colors"
                title={`View Issue #${token.content}`}
              >
                #{token.content}
              </Link>
            );

          case "link":
            return (
              <a
                key={i}
                href={token.content}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline break-all"
              >
                {token.content}
              </a>
            );

          case "bold":
            return (
              <strong key={i} className="font-bold text-black dark:text-white">
                {token.content}
              </strong>
            );

          case "italic":
            return (
              <em key={i} className="italic text-gray-800 dark:text-gray-200">
                {token.content}
              </em>
            );

          case "code":
            return (
              <code
                key={i}
                className="px-1.5 py-0.5 mx-0.5 bg-gray-100 dark:bg-gray-800 text-pink-600 dark:text-pink-400 font-mono text-sm rounded border border-gray-200 dark:border-gray-700"
              >
                {token.content}
              </code>
            );

          case "codeblock":
            return (
              <div
                key={i}
                className="my-3 rounded-lg overflow-hidden border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-[#0d0d0d]"
              >
                {token.metadata?.language && (
                  <div className="bg-gray-200 dark:bg-gray-800 px-3 py-1 text-xs font-mono text-gray-500 font-bold uppercase tracking-wider">
                    {token.metadata.language}
                  </div>
                )}
                <pre className="p-3 overflow-x-auto text-sm font-mono text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                  {token.content}
                </pre>
              </div>
            );

          case "quote":
            return (
              <blockquote
                key={i}
                className="pl-3 border-l-4 border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 my-2 italic bg-gray-50 dark:bg-gray-800/30 py-1 rounded-r"
              >
                {token.content}
              </blockquote>
            );

          default:
            return <span key={i}>{token.raw}</span>;
        }
      })}
    </div>
  );
}

// ============================================================================
// 4. Backwards Compatibility Wrapper
// ============================================================================

/**
 * Legacy compatible function that directly returns parsed React nodes.
 * Used for direct inline substitutions where the full block component isn't needed.
 */
export function renderWithMentions(text: string) {
  if (!text) return text;

  // We can just use the RichTextRenderer internally to return the component
  return <RichTextRenderer text={text} className="inline-renderer" />;
}
