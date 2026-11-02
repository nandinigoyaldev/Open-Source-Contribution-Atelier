/** The folder `git submodule add <url>` uses when no path is given: the repository name from the URL. */
export const DEFAULT_SUBMODULE_PATH = "libs/new-module";

/**
 * "https://github.com/atelier/core-utils.git" -> "core-utils". Handles a trailing slash, a missing
 * ".git", query strings and scp-style URLs ("git@github.com:atelier/core-utils.git"). Falls back to
 * DEFAULT_SUBMODULE_PATH when the URL has no usable last segment, so the result is never empty.
 */
export function deriveSubmodulePath(url: string | undefined): string {
  if (!url) return DEFAULT_SUBMODULE_PATH;
  const withoutQuery = url.trim().split(/[?#]/)[0];
  const lastSegment =
    withoutQuery.replace(/\/+$/, "").split(/[/:]/).pop() ?? "";
  const name = lastSegment.replace(/\.git$/i, "").trim();
  return name && name !== "." && name !== ".." ? name : DEFAULT_SUBMODULE_PATH;
}
