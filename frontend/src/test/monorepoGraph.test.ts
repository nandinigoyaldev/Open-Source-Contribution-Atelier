import { describe, expect, it } from "vitest";
import {
  INVALID_JSON_MESSAGE,
  PACKAGES_NOT_A_LIST_MESSAGE,
  describePackage,
  findCycles,
  highlightedIds,
  isEdgeInCycle,
  parseManifest,
  type PackageNode,
} from "../lib/monorepoGraph";

const manifest = (packages: unknown) =>
  JSON.stringify({ name: "ws", packages });

const node = (
  name: string,
  dependencies: string[] = [],
  extra: Partial<PackageNode> = {},
): PackageNode => ({
  id: name,
  name,
  version: "1.0.0",
  type: "package",
  dependencies,
  x: 0,
  y: 0,
  ...extra,
});

describe("parseManifest", () => {
  it("reads packages with their name, version, type and dependencies", () => {
    const result = parseManifest(
      manifest([
        {
          name: "@a/app",
          type: "app",
          version: "2.1.0",
          dependencies: ["@a/ui"],
        },
        { name: "@a/ui", type: "package" },
      ]),
    );
    expect(result.error).toBeNull();
    expect(result.warnings).toEqual([]);
    expect(
      result.packages.map((p) => [p.name, p.type, p.version, p.dependencies]),
    ).toEqual([
      ["@a/app", "app", "2.1.0", ["@a/ui"]],
      ["@a/ui", "package", "1.0.0", []],
    ]);
  });

  it("defaults a missing or unknown type to package and a missing version to 1.0.0", () => {
    const [a, b, c] = parseManifest(
      manifest([
        { name: "a" },
        { name: "b", type: "wizard", version: 3 },
        { name: "c", version: "" },
      ]),
    ).packages;
    expect([a.type, a.version]).toEqual(["package", "1.0.0"]);
    expect([b.type, b.version]).toEqual(["package", "1.0.0"]);
    expect(c.version).toBe("1.0.0");
  });

  it("accepts every package type the graph colours", () => {
    const types = parseManifest(
      manifest(
        ["app", "package", "utility", "service"].map((type) => ({
          name: type,
          type,
        })),
      ),
    ).packages.map((p) => p.type);
    expect(types).toEqual(["app", "package", "utility", "service"]);
  });

  it("reports invalid JSON as an error and shows nothing", () => {
    for (const text of ["", "{", "not json", "{'a': 1}", "[1, 2"]) {
      expect(parseManifest(text)).toEqual({
        packages: [],
        error: INVALID_JSON_MESSAGE,
        warnings: [],
      });
    }
  });

  it("reports JSON that is not an object as an error", () => {
    for (const text of ["[]", "5", '"text"', "null", "true"]) {
      expect(parseManifest(text).error).toBe(INVALID_JSON_MESSAGE);
    }
  });

  it("treats a manifest without a packages list as an empty workspace", () => {
    expect(parseManifest("{}")).toEqual({
      packages: [],
      error: null,
      warnings: [],
    });
    expect(parseManifest(JSON.stringify({ packages: [] })).packages).toEqual(
      [],
    );
  });

  it("reports a packages field that is not a list", () => {
    for (const value of ["x", 5, { a: 1 }, true]) {
      expect(parseManifest(JSON.stringify({ packages: value })).error).toBe(
        PACKAGES_NOT_A_LIST_MESSAGE,
      );
    }
  });

  it("skips entries without a usable name and says which", () => {
    const result = parseManifest(
      manifest([
        { name: "ok" },
        null,
        5,
        "text",
        [],
        {},
        { name: "" },
        { name: "  " },
        { name: 7 },
      ]),
    );
    expect(result.packages.map((p) => p.name)).toEqual(["ok"]);
    expect(result.warnings).toHaveLength(8);
    expect(result.warnings[0]).toBe(
      "Entry 2 was skipped: it has no package name.",
    );
    expect(result.error).toBeNull();
  });

  it("keeps the first of two packages with the same name", () => {
    const result = parseManifest(
      manifest([
        { name: "dup", version: "1.0.0" },
        { name: "dup", version: "9.9.9" },
      ]),
    );
    expect(result.packages).toHaveLength(1);
    expect(result.packages[0].version).toBe("1.0.0");
    expect(result.warnings).toEqual([
      'Entry 2 was skipped: "dup" is listed twice.',
    ]);
  });

  it("keeps only string dependencies", () => {
    const [pkg] = parseManifest(
      manifest([{ name: "a", dependencies: ["b", 3, null, { x: 1 }, "c"] }]),
    ).packages;
    expect(pkg.dependencies).toEqual(["b", "c"]);
    expect(
      parseManifest(manifest([{ name: "a", dependencies: "b" }])).packages[0]
        .dependencies,
    ).toEqual([]);
  });

  it("places packages on a circle around the centre, deterministically", () => {
    const names = ["a", "b", "c", "d"];
    const first = parseManifest(
      manifest(names.map((name) => ({ name }))),
    ).packages;
    const again = parseManifest(
      manifest(names.map((name) => ({ name }))),
    ).packages;
    expect(first).toEqual(again);
    expect(first[0]).toMatchObject({ x: 490, y: 240 }); // angle 0 on a 140px circle around (350, 240)
    for (const p of first) {
      expect(Math.hypot(p.x - 350, p.y - 240)).toBeGreaterThan(138);
      expect(Math.hypot(p.x - 350, p.y - 240)).toBeLessThan(142);
    }
  });

  it("uses a larger circle for more than five packages and handles a single one", () => {
    const many = parseManifest(
      manifest(Array.from({ length: 8 }, (_, i) => ({ name: `p${i}` }))),
    ).packages;
    expect(Math.hypot(many[1].x - 350, many[1].y - 240)).toBeGreaterThan(178);
    expect(
      parseManifest(manifest([{ name: "solo" }])).packages[0],
    ).toMatchObject({ x: 490, y: 240 });
  });

  it("copes with a large manifest", () => {
    const big = manifest(
      Array.from({ length: 2000 }, (_, i) => ({
        name: `p${i}`,
        dependencies: i ? [`p${i - 1}`] : [],
      })),
    );
    expect(parseManifest(big).packages).toHaveLength(2000);
  });
});

describe("findCycles", () => {
  it("finds nothing in a clean tree", () => {
    expect(
      findCycles([
        node("app", ["ui", "utils"]),
        node("ui", ["utils"]),
        node("utils"),
      ]),
    ).toEqual([]);
    expect(findCycles([])).toEqual([]);
  });

  it("finds a loop of two", () => {
    expect(findCycles([node("a", ["b"]), node("b", ["a"])])).toEqual([
      ["a", "b", "a"],
    ]);
  });

  it("finds a longer loop and ignores the packages that only lead into it", () => {
    const cycles = findCycles([
      node("app", ["a"]),
      node("a", ["b"]),
      node("b", ["c"]),
      node("c", ["a"]),
    ]);
    expect(cycles).toEqual([["a", "b", "c", "a"]]);
  });

  it("finds a package that depends on itself", () => {
    expect(findCycles([node("a", ["a"])])).toEqual([["a", "a"]]);
  });

  it("finds two separate loops", () => {
    const cycles = findCycles([
      node("a", ["b"]),
      node("b", ["a"]),
      node("x", ["y"]),
      node("y", ["x"]),
    ]);
    expect(cycles).toHaveLength(2);
  });

  it("does not report the same loop twice", () => {
    const cycles = findCycles([node("a", ["b", "b"]), node("b", ["a", "a"])]);
    expect(cycles).toEqual([["a", "b", "a"]]);
  });

  it("ignores dependencies on packages that are not in the workspace", () => {
    expect(
      findCycles([node("a", ["react", "lodash"]), node("b", ["a"])]),
    ).toEqual([]);
  });

  it("does not call a shared dependency (a diamond) a loop", () => {
    expect(
      findCycles([
        node("top", ["l", "r"]),
        node("l", ["base"]),
        node("r", ["base"]),
        node("base"),
      ]),
    ).toEqual([]);
  });

  it("handles a long chain without overflowing the stack", () => {
    const chain = Array.from({ length: 3000 }, (_, i) =>
      node(`p${i}`, i < 2999 ? [`p${i + 1}`] : []),
    );
    expect(findCycles(chain)).toEqual([]);
  });
});

describe("isEdgeInCycle", () => {
  const cycles = [["a", "b", "c", "a"]];

  it("is true for each step of a loop, in its direction only", () => {
    expect(isEdgeInCycle(cycles, "a", "b")).toBe(true);
    expect(isEdgeInCycle(cycles, "b", "c")).toBe(true);
    expect(isEdgeInCycle(cycles, "c", "a")).toBe(true);
    expect(isEdgeInCycle(cycles, "b", "a")).toBe(false);
  });

  it("is false for edges outside any loop", () => {
    expect(isEdgeInCycle(cycles, "a", "x")).toBe(false);
    expect(isEdgeInCycle([], "a", "b")).toBe(false);
  });
});

describe("highlightedIds", () => {
  const graph = [
    node("@a/app", ["@a/ui"]),
    node("@a/ui", ["@a/utils"]),
    node("@a/utils"),
    node("@a/other"),
  ];

  it("returns null when there is no search", () => {
    expect(highlightedIds(graph, "")).toBeNull();
    expect(highlightedIds(graph, "   ")).toBeNull();
  });

  it("returns the match with what it depends on and what depends on it", () => {
    expect([...highlightedIds(graph, "ui")!].sort()).toEqual([
      "@a/app",
      "@a/ui",
      "@a/utils",
    ]);
  });

  it("matches case-insensitively on part of the name", () => {
    expect(highlightedIds(graph, "UTIL")!.has("@a/utils")).toBe(true);
  });

  it("returns an empty set when nothing matches", () => {
    expect(highlightedIds(graph, "zzz")!.size).toBe(0);
  });

  it("does not highlight unrelated packages", () => {
    expect(highlightedIds(graph, "app")!.has("@a/other")).toBe(false);
  });
});

describe("describePackage", () => {
  const graph = [
    node("app", ["ui", "react"], { type: "app", version: "2.0.0" }),
    node("ui"),
    node("tool", ["app"]),
  ];

  it("says what the package is and how it connects", () => {
    expect(describePackage(graph[0], graph)).toBe(
      "app, v2.0.0, app. Depends on: ui. Used by: tool.",
    );
  });

  it("starts with the words the node shows, so speech control can use them", () => {
    expect(
      describePackage(graph[1], graph).startsWith("ui, v1.0.0, package"),
    ).toBe(true);
  });

  it("says none when there are no connections, and leaves out external packages", () => {
    expect(describePackage(graph[1], graph)).toBe(
      "ui, v1.0.0, package. Depends on: none. Used by: app.",
    );
    expect(describePackage(graph[2], graph)).toContain("Used by: none.");
  });
});
