import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../lib/api";

export type OpenApiParameter = {
  name: string;
  in: "path" | "query" | "header" | "cookie";
  required?: boolean;
  description?: string;
  schema?: OpenApiSchema;
  example?: unknown;
};

export type OpenApiSchema = {
  type?: string;
  format?: string;
  description?: string;
  example?: unknown;
  default?: unknown;
  enum?: unknown[];
  properties?: Record<string, OpenApiSchema>;
  items?: OpenApiSchema;
  required?: string[];
  nullable?: boolean;
  readOnly?: boolean;
  allOf?: OpenApiSchema[];
  oneOf?: OpenApiSchema[];
  anyOf?: OpenApiSchema[];
  $ref?: string;
};

export type OpenApiOperation = {
  summary?: string;
  description?: string;
  operationId?: string;
  tags?: string[];
  parameters?: OpenApiParameter[];
  requestBody?: {
    required?: boolean;
    content?: Record<string, { schema?: OpenApiSchema; example?: unknown }>;
  };
  responses?: Record<
    string,
    {
      description?: string;
      content?: Record<string, { schema?: OpenApiSchema; example?: unknown }>;
    }
  >;
};

export type OpenApiComponents = {
  schemas?: Record<string, OpenApiSchema>;
  parameters?: Record<string, OpenApiParameter>;
  requestBodies?: Record<string, unknown>;
  responses?: Record<string, unknown>;
};

export type OpenApiDocument = {
  info?: { title?: string; version?: string };
  paths?: Record<string, Record<string, OpenApiOperation>>;
  components?: OpenApiComponents;
};

export function useOpenApiSchema() {
  return useQuery({
    queryKey: ["openapi-schema"],
    queryFn: () => fetchApi("/schema/", { requireAuth: false }),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    select: (document) => document as OpenApiDocument,
  });
}
