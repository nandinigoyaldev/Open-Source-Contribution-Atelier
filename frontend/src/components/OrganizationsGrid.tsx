import React from "react";

interface Organization {
  id: string;
  name: string;
  description: string;
  logo?: string;
  status: "active" | "coming_soon";
}

const OrganizationsGrid: React.FC = () => {
  // Placeholder organizations
  const organizations: Organization[] = [
    {
      id: "1",
      name: "Open Source Initiative",
      description: "Leading open source organization",
      status: "coming_soon",
    },
    {
      id: "2",
      name: "GitHub Education",
      description: "GitHub student developer program",
      status: "coming_soon",
    },
    {
      id: "3",
      name: "Google Open Source",
      description: "Google open source programs",
      status: "coming_soon",
    },
  ];

  const activeOrgs = organizations.filter((org) => org.status === "active");
  const comingSoonOrgs = organizations.filter(
    (org) => org.status === "coming_soon",
  );

  return (
    <div className="w-full max-w-4xl mx-auto py-8 px-4">
      <div className="text-center mb-8">
        <h3 className="text-2xl font-bold text-gray-900 mb-3 flex items-center justify-center gap-2">
          <span>🏢</span> Supported Organizations
        </h3>
        <p className="text-gray-600 max-w-2xl mx-auto leading-relaxed">
          We're building partnerships with leading open source organizations to
          bring you real-world contribution opportunities. Start your open
          source journey with verified projects from trusted communities.
        </p>
      </div>

      {activeOrgs.length > 0 && (
        <div className="mb-10">
          <h4 className="text-lg font-black text-black dark:text-[#f0ebe2] mb-4">
            Active Partners
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {activeOrgs.map((org) => (
              <div
                key={org.id}
                className="flex items-start gap-4 p-5 bg-white border-4 border-black rounded-2xl shadow-card-sm hover:-translate-y-0.5 transition-all"
              >
                <span className="text-2xl p-2 bg-[#ffebc2] border-2 border-black rounded-xl">
                  🏗️
                </span>
                <div className="flex flex-col flex-1 min-w-0">
                  <span className="font-extrabold text-black dark:text-[#f0ebe2] truncate">
                    {org.name}
                  </span>
                  <span className="text-sm text-muted dark:text-[#9b8f80] mt-0.5 leading-snug">
                    {org.description}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-black bg-[#4ade80] border-2 border-black px-2.5 py-0.5 rounded-full w-fit mt-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-black"></span>{" "}
                    Active
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        {activeOrgs.length > 0 && (
          <h4 className="text-lg font-black text-black dark:text-[#f0ebe2] mb-4">
            Coming Soon
          </h4>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {comingSoonOrgs.map((org) => (
            <div
              key={org.id}
              className="flex items-start gap-4 p-5 bg-surface-low border-4 border-black dark:border-[#4a4238] rounded-2xl shadow-card-sm hover:-translate-y-0.5 transition-all"
            >
              <span className="text-2xl p-2 bg-[#ffb5e8] border-2 border-black dark:border-[#4a4238] rounded-xl">
                🚀
              </span>
              <div className="flex flex-col flex-1 min-w-0">
                <span className="font-extrabold text-black dark:text-[#f0ebe2] truncate">
                  {org.name}
                </span>
                <span className="text-sm text-muted dark:text-[#9b8f80] mt-0.5 leading-snug">
                  {org.description}
                </span>
                <span className="inline-flex items-center gap-1 text-xs font-bold text-black bg-[#ffcc00] border-2 border-black px-2.5 py-0.5 rounded-full w-fit mt-3">
                  <span className="w-1.5 h-1.5 rounded-full bg-black"></span>{" "}
                  Coming Soon
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-10 p-5 bg-[#C3C0FF] text-black border-4 border-black rounded-2xl flex items-start gap-3.5 max-w-2xl mx-auto shadow-card-sm">
        <span className="text-xl">💡</span>
        <p className="text-sm font-bold leading-relaxed m-0 text-black">
          Interested in featuring your organization? Contact us at{" "}
          <a
            href="mailto:partners@atelier.dev"
            className="text-black hover:underline transition font-black"
          >
            partners@atelier.dev
          </a>
        </p>
      </div>
    </div>
  );
};

export default OrganizationsGrid;
