import React from 'react';
import { ORGS } from '../lib/organizations';

const OrganizationsGrid: React.FC = () => {
  return (
    <section aria-labelledby="orgs-heading" className="mb-6">
      <h3 id="orgs-heading" className="text-xs font-black uppercase tracking-wider text-muted mb-3 text-center">
        Supported Orgs
      </h3>
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3">
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