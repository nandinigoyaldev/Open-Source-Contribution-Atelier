import { describe, expect, it } from "vitest";
import type {
  OpenApiComponents,
  OpenApiOperation,
} from "../../hooks/useOpenApiSchema";
import { resolveOperationRefs, resolveSchemaRefs } from "../openApiRefs";

const components: OpenApiComponents = {
  schemas: {
    Role: { type: "string", enum: ["learner", "mentor"] },
    User: {
      type: "object",
      required: ["id"],
      properties: {
        id: { type: "integer" },
        role: { $ref: "#/components/schemas/Role" },
      },
    },
    Team: {
      type: "object",
      properties: {
        members: {
          type: "array",
          items: { $ref: "#/components/schemas/User" },
        },
      },
    },
    Node: {
      type: "object",
      properties: {
        name: { type: "string" },
        parent: { $ref: "#/components/schemas/Node" },
      },
    },
    Timestamps: {
      type: "object",
      required: ["created"],
      properties: { created: { type: "string", format: "date-time" } },
    },
  },
  parameters: {
    Page: { name: "page", in: "query", description: "Page number" },
  },
};

describe("resolveSchemaRefs (Issue #3075)", () => {
  it("replaces a $ref with the schema it points to", () => {
    expect(
      resolveSchemaRefs({ $ref: "#/components/schemas/Role" }, components),
    ).toEqual({ type: "string", enum: ["learner", "mentor"] });
  });

  it("resolves references nested in properties, arrays and other references", () => {
    const team = resolveSchemaRefs(
      { $ref: "#/components/schemas/Team" },
      components,
    );
    const member = team?.properties?.members.items;
    expect(member?.properties?.id).toEqual({ type: "integer" });
    expect(member?.properties?.role?.enum).toEqual(["learner", "mentor"]);
  });

  it("keeps sibling keywords written next to a $ref", () => {
    const schema = resolveSchemaRefs(
      { $ref: "#/components/schemas/Role", description: "Account role" },
      components,
    );
    expect(schema?.description).toBe("Account role");
    expect(schema?.enum).toEqual(["learner", "mentor"]);
  });

  it("merges allOf parts into one schema", () => {
    const merged = resolveSchemaRefs(
      {
        allOf: [
          { $ref: "#/components/schemas/User" },
          { $ref: "#/components/schemas/Timestamps" },
          { type: "object", required: ["role"], properties: { note: { type: "string" } } },
        ],
        description: "User with timestamps",
      },
      components,
    );
    expect(Object.keys(merged?.properties ?? {}).sort()).toEqual([
      "created",
      "id",
      "note",
      "role",
    ]);
    expect(merged?.required?.sort()).toEqual(["created", "id", "role"]);
    expect(merged?.description).toBe("User with timestamps");
    expect(merged?.allOf).toBeUndefined();
  });

  it("stops at a reference that points back to itself instead of looping", () => {
    const node = resolveSchemaRefs(
      { $ref: "#/components/schemas/Node" },
      components,
    );
    expect(node?.properties?.name).toEqual({ type: "string" });
    expect(node?.properties?.parent?.description).toMatch(/recursive/i);
    expect(node?.properties?.parent?.properties).toBeUndefined();
  });

  it("stops at an absurdly deep chain of references", () => {
    const schemas: Record<string, { $ref?: string; type?: string }> = {};
    for (let i = 0; i < 30; i += 1) {
      schemas[`S${i}`] = i === 29 ? { type: "string" } : { $ref: `#/components/schemas/S${i + 1}` };
    }
    const out = resolveSchemaRefs({ $ref: "#/components/schemas/S0" }, { schemas });
    expect(out?.description).toMatch(/recursive/i);
  });

  it("notes a reference it cannot find rather than throwing", () => {
    const out = resolveSchemaRefs(
      { $ref: "#/components/schemas/Missing" },
      components,
    );
    expect(out?.description).toContain("#/components/schemas/Missing");
  });

  it("leaves $ref text inside examples and defaults alone", () => {
    const out = resolveSchemaRefs(
      {
        type: "object",
        example: { $ref: "#/components/schemas/Role" },
        default: { $ref: "x" },
      },
      components,
    );
    expect(out?.example).toEqual({ $ref: "#/components/schemas/Role" });
    expect(out?.default).toEqual({ $ref: "x" });
  });

  it("returns the input untouched when there are no components", () => {
    const schema = { $ref: "#/components/schemas/Role" };
    expect(resolveSchemaRefs(schema, undefined)).toBe(schema);
    expect(resolveSchemaRefs(undefined, components)).toBeUndefined();
  });

  it("does not modify the original document", () => {
    const schema = { $ref: "#/components/schemas/User" };
    const before = JSON.stringify([schema, components]);
    resolveSchemaRefs(schema, components);
    expect(JSON.stringify([schema, components])).toBe(before);
  });
});

describe("resolveOperationRefs (Issue #3075)", () => {
  const operation: OpenApiOperation = {
    summary: "Create user",
    parameters: [{ $ref: "#/components/parameters/Page" } as never],
    requestBody: {
      content: {
        "application/json": { schema: { $ref: "#/components/schemas/User" } },
      },
    },
    responses: {
      "201": {
        description: "Created",
        content: {
          "application/json": { schema: { $ref: "#/components/schemas/Team" } },
        },
      },
    },
  };

  it("resolves parameters, the request body and responses", () => {
    const out = resolveOperationRefs(operation, components);
    expect(out.parameters?.[0]).toMatchObject({ name: "page", in: "query" });
    expect(
      out.requestBody?.content?.["application/json"]?.schema?.properties?.id,
    ).toEqual({ type: "integer" });
    expect(
      out.responses?.["201"].content?.["application/json"]?.schema?.properties
        ?.members.items?.properties?.id,
    ).toEqual({ type: "integer" });
    expect(out.summary).toBe("Create user");
  });

  it("returns the same operation when there are no components", () => {
    expect(resolveOperationRefs(operation, undefined)).toBe(operation);
  });
});
