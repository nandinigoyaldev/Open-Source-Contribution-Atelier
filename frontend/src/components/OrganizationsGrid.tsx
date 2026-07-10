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
          <h4 className="text-lg font-semibold text-gray-700 mb-4">
            Active Partners
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {activeOrgs.map((org) => (
              <div
                key={org.id}
                className="flex items-start gap-4 p-5 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-md transition duration-200"
              >
                <span className="text-2xl p-2 bg-blue-50 rounded-xl">🏗️</span>
                <div className="flex flex-col flex-1 min-w-0">
                  <span className="font-bold text-gray-900 truncate">
                    {org.name}
                  </span>
                  <span className="text-sm text-gray-500 mt-0.5 leading-snug">
                    {org.description}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-50 px-2.5 py-1 rounded-full w-fit mt-3">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>{" "}
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
          <h4 className="text-lg font-semibold text-gray-700 mb-4">
            Coming Soon
          </h4>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {comingSoonOrgs.map((org) => (
            <div
              key={org.id}
              className="flex items-start gap-4 p-5 bg-gray-50/50 border border-gray-150 rounded-2xl shadow-sm hover:shadow-md transition duration-200"
            >
              <span className="text-2xl p-2 bg-amber-50 rounded-xl">🚀</span>
              <div className="flex flex-col flex-1 min-w-0">
                <span className="font-bold text-gray-800 truncate">
                  {org.name}
                </span>
                <span className="text-sm text-gray-500 mt-0.5 leading-snug">
                  {org.description}
                </span>
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full w-fit mt-3">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>{" "}
                  Coming Soon
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-10 p-5 bg-blue-50/40 border border-blue-100 rounded-2xl flex items-start gap-3.5 max-w-2xl mx-auto">
        <span className="text-xl">💡</span>
        <p className="text-sm text-gray-600 leading-relaxed m-0">
          Interested in featuring your organization? Contact us at{" "}
          <a
            href="mailto:partners@atelier.dev"
            className="text-blue-600 hover:text-blue-700 font-medium underline transition"
          >
            partners@atelier.dev
          </a>
        </p>
      </div>
    </div>
  );
};

export default OrganizationsGrid;
