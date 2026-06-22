import React, { useState, useEffect } from 'react';

const OrganizationsGrid: React.FC = () => {
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // API Call to our new backend endpoint
    fetch('http://127.0.0.1:8000/api/content/organizations/')
      .then((res) => res.json())
      .then((data) => {
        setOrganizations(data);
        setLoading(false);
      })
      .catch((err) => console.error("Error fetching organizations:", err));
  }, []);

  if (loading) return <div className="text-center">Loading Organizations...</div>;

  return (
    <section aria-labelledby="orgs-heading" className="mb-6">
      <h3 id="orgs-heading" className="text-xs font-black uppercase tracking-wider text-muted mb-3 text-center">
        Supported Orgs
      </h3>

      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3">
        {organizations.map((org) => (
          <a
            key={org.slug}
            href={`https://github.com/${org.slug}`}
            target="_blank"
            rel="noopener noreferrer"
            className="border-2 border-black rounded-xl p-2.5 flex items-center gap-2 hover:-translate-y-0.5 transition-all bg-white"
          >
            <img
              src={org.logo_url || `https://github.com/${org.slug}.png?size=80`}
              alt={`${org.name} avatar`}
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
