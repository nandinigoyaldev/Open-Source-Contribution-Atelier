import type {
  OpenApiComponents,
  OpenApiOperation,
  OpenApiSchema,
} from "../hooks/useOpenApiSchema";

// The backend schema (drf-spectacular) keeps request and response shapes in
// components.schemas and points at them with "$ref". The docs page needs the real shapes,
// so references are replaced with what they point to.

// A reference that loops back to itself, or nests deeper than this, is cut off with a note.
const MAX_REF_DEPTH = 8;

// Values the author wrote by hand; a "$ref" key inside them is data, not a reference.
const LITERAL_KEYS = new Set(["example", "examples", "default", "enum"]);

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function lookup(ref: string, components: OpenApiComponents): unknown {
  const match = /^#\/components\/([^/]+)\/(.+)$/.exec(ref);
  if (!match) return undefined;
  const group = components[match[1] as keyof OpenApiComponents] as
    | Record<string, unknown>
    | undefined;
  return group?.[match[2]];
}

function refName(ref: string): string {
  return ref.split("/").pop() ?? ref;
}

// Combine allOf parts into one schema: properties and required lists are joined, and the
// schema's own keywords win over the parts'.
function mergeAllOf(schema: OpenApiSchema): OpenApiSchema {
  const { allOf, ...own } = schema;
  if (!allOf?.length) return schema;

  const merged: OpenApiSchema = {};
  for (const part of allOf) {
    const { properties, required, ...rest } = mergeAllOf(part);
    Object.assign(merged, rest);
    if (properties) merged.properties = { ...merged.properties, ...properties };
    if (required) {
      merged.required = [...new Set([...(merged.required ?? []), ...required])];
    }
  }
  const { properties, required, ...ownRest } = own;
  Object.assign(merged, ownRest);
  if (properties) merged.properties = { ...merged.properties, ...properties };
  if (required) {
    merged.required = [...new Set([...(merged.required ?? []), ...required])];
  }
  return merged;
}

function walk(
  node: unknown,
  components: OpenApiComponents,
  trail: string[],
): unknown {
  if (Array.isArray(node)) {
    return node.map((item) => walk(item, components, trail));
  }
  if (!isRecord(node)) return node;

  if (typeof node.$ref === "string") {
    const { $ref: ref, ...siblings } = node;
    const name = refName(ref);
    if (trail.includes(ref) || trail.length >= MAX_REF_DEPTH) {
      return { type: "object", description: `${name} (recursive reference)` };
    }
    const target = lookup(ref, components);
    if (target === undefined) {
      return { description: `Unresolved reference ${ref}`, ...siblings };
    }
    const resolved = walk(target, components, [...trail, ref]);
    return isRecord(resolved) ? { ...resolved, ...siblings } : resolved;
  }

  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(node)) {
    out[key] = LITERAL_KEYS.has(key) ? value : walk(value, components, trail);
  }
  return Array.isArray(out.allOf) ? mergeAllOf(out as OpenApiSchema) : out;
}

export function resolveSchemaRefs(
  schema: OpenApiSchema | undefined,
  components: OpenApiComponents | undefined,
): OpenApiSchema | undefined {
  if (!schema || !components) return schema;
  return walk(schema, components, []) as OpenApiSchema;
}

export function resolveOperationRefs(
  operation: OpenApiOperation,
  components: OpenApiComponents | undefined,
): OpenApiOperation {
  if (!components) return operation;
  return walk(operation, components, []) as OpenApiOperation;
}
