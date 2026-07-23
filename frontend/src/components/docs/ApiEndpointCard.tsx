import { useState } from "react";
import { Play, Send } from "lucide-react";
import { API_BASE } from "../../lib/api";
import { getAccessToken } from "../../lib/authToken";
import type {
  OpenApiOperation,
  OpenApiParameter,
  OpenApiSchema,
} from "../../hooks/useOpenApiSchema";

type ApiEndpointCardProps = {
  method: string;
  path: string;
  operation: OpenApiOperation;
};

const methodClasses: Record<string, string> = {
  get: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  post: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
  put: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  patch: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  delete: "bg-red-500/15 text-red-700 dark:text-red-300",
};

function exampleForSchema(schema?: OpenApiSchema): unknown {
  if (!schema) return {};
  if (schema.example !== undefined) return schema.example;
  if (schema.default !== undefined) return schema.default;
  if (schema.enum?.length) return schema.enum[0];
  if (schema.type === "array") return [exampleForSchema(schema.items)];
  if (schema.type === "object" || schema.properties) {
    return Object.fromEntries(
      Object.entries(schema.properties ?? {}).map(([name, property]) => [
        name,
        exampleForSchema(property),
      ]),
    );
  }
  if (schema.type === "integer" || schema.type === "number") return 0;
  if (schema.type === "boolean") return false;
  return "string";
}

function SchemaPreview({ schema }: { schema?: OpenApiSchema }) {
  if (!schema) return <span className="text-muted">No schema documented.</span>;

  return (
    <pre className="overflow-x-auto rounded-lg bg-black/5 p-3 text-xs text-text dark:bg-white/10 dark:text-[#f0ebe2]">
      {JSON.stringify(exampleForSchema(schema), null, 2)}
    </pre>
  );
}

function ParameterList({ parameters }: { parameters: OpenApiParameter[] }) {
  if (!parameters.length) return null;

  return (
    <div>
      <h4 className="mb-2 font-semibold">Parameters</h4>
      <ul className="space-y-1 text-sm text-muted dark:text-[#c4bbae]">
        {parameters.map((parameter) => (
          <li key={`${parameter.in}-${parameter.name}`}>
            <code>{parameter.name}</code> <span>({parameter.in})</span>
            {parameter.required ? " required" : ""}
            {parameter.description ? ` — ${parameter.description}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ApiEndpointCard({
  method,
  path,
  operation,
}: ApiEndpointCardProps) {
  const [isTrying, setIsTrying] = useState(false);
  const [requestPath, setRequestPath] = useState(path);
  const [requestBody, setRequestBody] = useState(() => {
    const media = operation.requestBody?.content?.["application/json"];
    return media
      ? JSON.stringify(media.example ?? exampleForSchema(media.schema), null, 2)
      : "";
  });
  const [result, setResult] = useState<string | null>(null);
  const parameters = operation.parameters ?? [];
  const response = Object.entries(operation.responses ?? {})[0];
  const responseSchema = response?.[1].content?.["application/json"]?.schema;

  async function sendRequest() {
    if (method !== "get" && !window.confirm("Send this request to the API?"))
      return;

    try {
      const headers = new Headers({ Accept: "application/json" });
      const token = getAccessToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);

      const options: RequestInit = { method: method.toUpperCase(), headers };
      if (requestBody.trim()) {
        JSON.parse(requestBody);
        headers.set("Content-Type", "application/json");
        options.body = requestBody;
      }

      const response = await fetch(`${API_BASE}${requestPath}`, options);
      const body = await response.text();
      setResult(`${response.status} ${response.statusText}\n${body}`);
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  return (
    <article className="space-y-4 rounded-xl border border-black/10 bg-surface p-5 shadow-sm dark:border-white/10 dark:bg-[#12121a]">
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`rounded px-2 py-1 text-xs font-bold uppercase ${methodClasses[method] ?? "bg-black/10"}`}
        >
          {method}
        </span>
        <code className="break-all font-semibold">{path}</code>
      </div>
      <div>
        <h3 className="text-lg font-bold">
          {operation.summary || operation.operationId || path}
        </h3>
        {operation.description && (
          <p className="mt-1 text-sm text-muted dark:text-[#c4bbae]">
            {operation.description}
          </p>
        )}
      </div>

      <ParameterList parameters={parameters} />

      {operation.requestBody && (
        <div>
          <h4 className="mb-2 font-semibold">Request body</h4>
          <SchemaPreview
            schema={operation.requestBody.content?.["application/json"]?.schema}
          />
        </div>
      )}

      {response && (
        <div>
          <h4 className="mb-2 font-semibold">Response {response[0]}</h4>
          <SchemaPreview schema={responseSchema} />
        </div>
      )}

      <button
        type="button"
        onClick={() => setIsTrying((current) => !current)}
        className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-semibold text-white"
      >
        <Play size={16} /> Try it
      </button>

      {isTrying && (
        <div className="space-y-3 rounded-lg border border-black/10 p-4 dark:border-white/10">
          <label className="block text-sm font-medium">
            Request path
            <input
              value={requestPath}
              onChange={(event) => setRequestPath(event.target.value)}
              className="mt-1 w-full rounded border border-black/20 bg-transparent px-3 py-2 font-mono text-sm dark:border-white/20"
            />
          </label>
          {operation.requestBody && (
            <label className="block text-sm font-medium">
              JSON body
              <textarea
                value={requestBody}
                onChange={(event) => setRequestBody(event.target.value)}
                rows={8}
                className="mt-1 w-full rounded border border-black/20 bg-transparent p-3 font-mono text-sm dark:border-white/20"
              />
            </label>
          )}
          <button
            type="button"
            onClick={sendRequest}
            className="inline-flex items-center gap-2 rounded-md border border-primary px-3 py-2 text-sm font-semibold text-primary"
          >
            <Send size={16} /> Send request
          </button>
          {result && (
            <pre className="max-h-64 overflow-auto rounded bg-black/5 p-3 text-xs dark:bg-white/10">
              {result}
            </pre>
          )}
        </div>
      )}
    </article>
  );
}
