import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import { ApiEndpointCard } from "../components/docs/ApiEndpointCard";
import { SectionCard } from "../components/ui/SectionCard";
import { API_BASE } from "../lib/api";
import { useOpenApiSchema } from "../hooks/useOpenApiSchema";

const httpMethods = new Set([
  "get",
  "post",
  "put",
  "patch",
  "delete",
  "head",
  "options",
]);

export function ApiDocsPage() {
  const [search, setSearch] = useState("");
  const { data: schema, isLoading, isError } = useOpenApiSchema();
  const endpoints = useMemo(() => {
    const query = search.trim().toLowerCase();
    return Object.entries(schema?.paths ?? {}).flatMap(([path, operations]) =>
      Object.entries(operations)
        .filter(([method]) => httpMethods.has(method))
        .map(([method, operation]) => ({ method, path, operation }))
        .filter(
          ({ method, path, operation }) =>
            !query ||
            [
              method,
              path,
              operation.summary,
              operation.operationId,
              ...(operation.tags ?? []),
            ]
              .filter(Boolean)
              .join(" ")
              .toLowerCase()
              .includes(query),
        ),
    );
  }, [schema, search]);

  const groupedEndpoints = useMemo(() => {
    return endpoints.reduce<Record<string, typeof endpoints>>(
      (groups, endpoint) => {
        const tag = endpoint.operation.tags?.[0] ?? "Other";
        (groups[tag] ??= []).push(endpoint);
        return groups;
      },
      {},
    );
  }, [endpoints]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-16">
      <SectionCard
        eyebrow="Developer reference"
        title={schema?.info?.title || "API documentation"}
      >
        <p className="text-sm text-muted dark:text-[#c4bbae]">
          Interactive reference generated from the current OpenAPI schema
          {schema?.info?.version ? ` (v${schema.info.version})` : ""}.
        </p>
      </SectionCard>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block max-w-xl flex-1">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
          <input
            aria-label="Search API endpoints"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, method, path, or tag"
            className="w-full rounded-lg border border-black/15 bg-surface py-2 pl-10 pr-3 dark:border-white/15 dark:bg-[#12121a]"
          />
        </label>
        <div className="flex gap-2">
          <a
            href={`${API_BASE}/schema/?format=json`}
            download
            className="inline-flex items-center gap-2 rounded-md border border-black/15 px-3 py-2 text-sm font-semibold dark:border-white/15"
          >
            <Download size={16} /> JSON
          </a>
          <a
            href={`${API_BASE}/schema/?format=openapi`}
            download
            className="inline-flex items-center gap-2 rounded-md border border-black/15 px-3 py-2 text-sm font-semibold dark:border-white/15"
          >
            <Download size={16} /> YAML
          </a>
        </div>
      </div>

      <section
        aria-label="Schema changelog"
        className="rounded-xl border border-black/10 p-4 text-sm text-muted dark:border-white/10 dark:text-[#c4bbae]"
      >
        <strong className="text-text dark:text-[#f0ebe2]">
          Schema changelog
        </strong>
        <p className="mt-1">
          The schema exposes its current version
          {schema?.info?.version ? ` as v${schema.info.version}` : ""}.
          Historical schema snapshots are not available yet.
        </p>
      </section>

      {isLoading && <p role="status">Loading API documentation…</p>}
      {isError && (
        <p role="alert">
          Unable to load the API schema. Please try again later.
        </p>
      )}
      {!isLoading && !isError && endpoints.length === 0 && (
        <p>No endpoints match your search.</p>
      )}

      {Object.entries(groupedEndpoints)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([tag, tagEndpoints]) => (
          <section
            key={tag}
            aria-labelledby={`tag-${tag}`}
            className="space-y-3"
          >
            <h2 id={`tag-${tag}`} className="text-xl font-bold capitalize">
              {tag}
            </h2>
            {tagEndpoints.map((endpoint) => (
              <ApiEndpointCard
                key={`${endpoint.method}-${endpoint.path}`}
                {...endpoint}
              />
            ))}
          </section>
        ))}
    </div>
  );
}
