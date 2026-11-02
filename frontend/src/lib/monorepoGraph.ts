/**
 * Pure helpers behind the Monorepo Dependency Graph (components/monorepo/MonorepoDependencyGraph.tsx):
 * reading a workspace manifest, laying the packages out, finding circular dependencies and working out
 * which packages to highlight for a search. No React and no browser APIs, so they are unit tested on
 * their own (src/test/monorepoGraph.test.ts).
 */

export type PackageType = "app" | "package" | "utility" | "service";

export interface PackageNode {
  id: string;
  name: string;
  version: string;
  dependencies: string[];
  type: PackageType;
  x: number;
  y: number;
}

export interface ManifestParse {
  packages: PackageNode[];
  /** A problem that makes the whole manifest unusable. */
  error: string | null;
  /** Entries that were skipped, each with the reason. The rest of the manifest is still shown. */
  warnings: string[];
}

export const INVALID_JSON_MESSAGE =
  "Invalid JSON manifest syntax. Please verify formatting.";
export const PACKAGES_NOT_A_LIST_MESSAGE =
  'The manifest\'s "packages" field must be a list.';

const PACKAGE_TYPES: PackageType[] = ["app", "package", "utility", "service"];

const LAYOUT = {
  centerX: 350,
  centerY: 240,
  smallRadius: 140,
  largeRadius: 180,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Reads the manifest text. A package is usable when it has a non-empty string `name`; anything else in
 * the list is skipped with a warning instead of breaking the graph. Duplicate names keep the first
 * entry. `dependencies` keeps only strings; a dependency on a package that is not listed is allowed
 * (it is an external package) and simply draws no edge.
 */
export function parseManifest(json: string): ManifestParse {
  let parsed: unknown;
  try {
    parsed = JSON.parse(json);
  } catch {
    return { packages: [], error: INVALID_JSON_MESSAGE, warnings: [] };
  }

  if (!isRecord(parsed)) {
    return { packages: [], error: INVALID_JSON_MESSAGE, warnings: [] };
  }

  const rawList = parsed.packages ?? [];
  if (!Array.isArray(rawList)) {
    return { packages: [], error: PACKAGES_NOT_A_LIST_MESSAGE, warnings: [] };
  }

  const warnings: string[] = [];
  const seen = new Set<string>();
  const accepted: Record<string, unknown>[] = [];

  rawList.forEach((entry, index) => {
    if (
      !isRecord(entry) ||
      typeof entry.name !== "string" ||
      !entry.name.trim()
    ) {
      warnings.push(`Entry ${index + 1} was skipped: it has no package name.`);
      return;
    }
    if (seen.has(entry.name)) {
      warnings.push(
        `Entry ${index + 1} was skipped: "${entry.name}" is listed twice.`,
      );
      return;
    }
    seen.add(entry.name);
    accepted.push(entry);
  });

  const count = accepted.length;
  const radius = count > 5 ? LAYOUT.largeRadius : LAYOUT.smallRadius;

  const packages = accepted.map((pkg, idx): PackageNode => {
    const angle = (idx / Math.max(count, 1)) * 2 * Math.PI;
    const type = PACKAGE_TYPES.includes(pkg.type as PackageType)
      ? (pkg.type as PackageType)
      : "package";
    return {
      id: pkg.name as string,
      name: pkg.name as string,
      version:
        typeof pkg.version === "string" && pkg.version ? pkg.version : "1.0.0",
      type,
      dependencies: Array.isArray(pkg.dependencies)
        ? pkg.dependencies.filter(
            (dep): dep is string => typeof dep === "string",
          )
        : [],
      x: Math.round(LAYOUT.centerX + radius * Math.cos(angle)),
      y: Math.round(LAYOUT.centerY + radius * Math.sin(angle)),
    };
  });

  return { packages, error: null, warnings };
}

/**
 * Circular dependency loops, each as a path that ends where it started (["a", "b", "a"]).
 * A package that depends on itself is a loop ["a", "a"]. Dependencies on packages that are not in the
 * list are ignored. Every distinct loop is reported once.
 */
export function findCycles(packages: PackageNode[]): string[][] {
  const adjacency = new Map<string, string[]>();
  packages.forEach((pkg) => adjacency.set(pkg.id, pkg.dependencies));

  const cycles: string[][] = [];
  const known = new Set<string>();
  const visited = new Set<string>();
  const onStack = new Set<string>();

  const visit = (current: string, path: string[]) => {
    visited.add(current);
    onStack.add(current);
    path.push(current);

    for (const next of adjacency.get(current) ?? []) {
      if (!adjacency.has(next)) continue;
      if (!visited.has(next)) {
        visit(next, [...path]);
      } else if (onStack.has(next)) {
        const start = path.indexOf(next);
        if (start !== -1) {
          const loop = [...path.slice(start), next];
          const key = loop.join("->");
          if (!known.has(key)) {
            known.add(key);
            cycles.push(loop);
          }
        }
      }
    }
    onStack.delete(current);
  };

  packages.forEach((pkg) => {
    if (!visited.has(pkg.id)) visit(pkg.id, []);
  });
  return cycles;
}

/** True when the edge source -> target is one step of a detected loop. */
export function isEdgeInCycle(
  cycles: string[][],
  sourceId: string,
  targetId: string,
): boolean {
  return cycles.some((cycle) =>
    cycle.some(
      (id, i) =>
        i < cycle.length - 1 && id === sourceId && cycle[i + 1] === targetId,
    ),
  );
}

/**
 * Packages to keep in full colour for a search: the matches (case-insensitive substring of the name),
 * what they depend on, and what depends on them. null means "no filter" (empty query); an empty set
 * means "nothing matched".
 */
export function highlightedIds(
  packages: PackageNode[],
  query: string,
): Set<string> | null {
  const wanted = query.trim().toLowerCase();
  if (!wanted) return null;

  const highlighted = new Set<string>();
  packages
    .filter((pkg) => pkg.name.toLowerCase().includes(wanted))
    .forEach((target) => {
      highlighted.add(target.id);
      target.dependencies.forEach((dep) => highlighted.add(dep));
      packages.forEach((other) => {
        if (other.dependencies.includes(target.id)) highlighted.add(other.id);
      });
    });
  return highlighted;
}

/**
 * The accessible name of a package node: what it is and how it connects.
 * It starts with the same words the node shows ("name", then "v1.0.0" and the type), so speech-control
 * users can say what they see (WCAG 2.5.3 Label in Name), and then adds the connections.
 */
export function describePackage(
  pkg: PackageNode,
  packages: PackageNode[],
): string {
  const known = new Set(packages.map((p) => p.id));
  const uses = pkg.dependencies.filter((dep) => known.has(dep));
  const usedBy = packages
    .filter((p) => p.dependencies.includes(pkg.id))
    .map((p) => p.name);
  const list = (names: string[]) => (names.length ? names.join(", ") : "none");
  return `${pkg.name}, v${pkg.version}, ${pkg.type}. Depends on: ${list(uses)}. Used by: ${list(usedBy)}.`;
}
