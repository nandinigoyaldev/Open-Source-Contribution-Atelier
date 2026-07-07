import React, { useState, useEffect } from "react";
import { OptimizedImage } from "./ui/OptimizedImage";
import SkeletonCard from "./ui/skeletons/SkeletonCard";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.trim() || `${window.location.origin}/api`;

type Organization = {
  slug: string;
  name: string;
  logo_url?: string | null;
  logoUrl?: string | null;
};

const DEFAULT_ORGANIZATIONS: Organization[] = [
  { slug: "facebook", name: "React" },
  { slug: "vercel", name: "Next.js" },
  { slug: "django", name: "Django" },
  { slug: "kubernetes", name: "Kubernetes" },
  { slug: "microsoft", name: "VS Code" },
  { slug: "nodejs", name: "Node.js" },
];

const normalizeImageUrl = (url: string, baseUrl: string) => {
  if (!url) return url;

  try {
    return new URL(url, baseUrl).toString();
  } catch {
    return url;
  }
};

const OrganizationsGrid: React.FC = () => {
  const [organizations, setOrganizations] = useState<Organization[]>(
    DEFAULT_ORGANIZATIONS,
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/content/organizations/`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setOrganizations(
          Array.isArray(data) && data.length > 0
            ? data
            : DEFAULT_ORGANIZATIONS,
        );
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching organizations:", err);
        setOrganizations(DEFAULT_ORGANIZATIONS);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <section aria-labelledby="orgs-heading" className="mb-6">
        <h3
          id="orgs-heading"
          className="text-xs font-black uppercase tracking-wider text-muted mb-3 text-center"
        >
          Supported Orgs
        </h3>

        <div className="grid gap-3 grid-cols-2 md:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="orgs-heading" className="mb-6">
      <h3
        id="orgs-heading"
        className="text-xs font-black uppercase tracking-wider text-muted mb-3 text-center"
      >
        Supported Orgs
      </h3>

      <div className="grid gap-3 grid-cols-2 md:grid-cols-3">
        {organizations.map((org) => (
          <a
            key={org.slug}
            href={`https://github.com/${org.slug}`}
            target="_blank"
            rel="noopener noreferrer"
            className="border-2 border-black rounded-lg p-2.5 flex items-center gap-2 hover:-translate-y-0.5 transition-all bg-white"
          >
            <OptimizedImage
              src={normalizeImageUrl(
                org.logo_url ||
                  org.logoUrl ||
                  `https://github.com/${org.slug}.png?size=80`,
                API_BASE,
              )}
              alt={`${org.name} avatar`}
              width={32}
              height={32}
              loading="eager"
              className="w-8 h-8 rounded-lg object-cover border border-black/20"
            />
            <div className="truncate min-w-0">
              <div className="font-bold text-xs truncate uppercase tracking-tight">
                {org.name}
              </div>
              <div className="text-[10px] text-muted truncate">GitHub</div>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
};

export default OrganizationsGrid;
