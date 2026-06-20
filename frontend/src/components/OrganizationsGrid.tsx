import React from "react";
import { ORGS } from "../lib/organizations";

const OrganizationsGrid: React.FC = () => {
  return (
    <section aria-labelledby="orgs-heading" className="mt-8">
      <h3 id="orgs-heading" className="text-lg font-semibold mb-4">
        Open-source organizations
      </h3>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
        {ORGS.map((slug) => (
          <a
            key={slug}
            href={`https://github.com/${slug}`}
            target="_blank"
            rel="noopener noreferrer"
            className="border-2 border-black rounded-xl p-2.5 flex items-center gap-2 hover:-translate-y-0.5 transition-all bg-white dark:bg-gray-800 shadow-card-sm hover:shadow-card cursor-pointer"
          >
            <img
              src={`https://github.com/${slug}.png?size=80`}
              alt={`${slug} avatar`}
              className="w-8 h-8 rounded-lg object-cover border border-black/20"
            />
            <div className="truncate min-w-0">
              <div className="font-bold text-xs truncate uppercase tracking-tight">{slug}</div>
              <div className="text-[10px] text-muted truncate">GitHub</div>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
};

export default OrganizationsGrid;
