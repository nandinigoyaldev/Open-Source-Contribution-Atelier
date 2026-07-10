import React from 'react';

interface Organization {
  id: string;
  name: string;
  description: string;
  logo?: string;
  status: 'active' | 'coming_soon';
}

const OrganizationsGrid: React.FC = () => {
  // Placeholder organizations
  const organizations: Organization[] = [
    {
      id: '1',
      name: 'Open Source Initiative',
      description: 'Leading open source organization',
      status: 'coming_soon'
    },
    {
      id: '2', 
      name: 'GitHub Education',
      description: 'GitHub student developer program',
      status: 'coming_soon'
    },
    {
      id: '3',
      name: 'Google Open Source',
      description: 'Google open source programs',
      status: 'coming_soon'
    }
  ];

  const activeOrgs = organizations.filter(org => org.status === 'active');
  const comingSoonOrgs = organizations.filter(org => org.status === 'coming_soon');

  return (
    <div className="organizations-grid-container">
      <div className="org-section-header">
        <h3 className="org-title">🏢 Supported Organizations</h3>
        <p className="org-description">
          We're building partnerships with leading open source organizations to bring 
          you real-world contribution opportunities. Start your open source journey 
          with verified projects from trusted communities.
        </p>
      </div>

      {activeOrgs.length > 0 ? (
        <div className="org-grid">
          {activeOrgs.map(org => (
            <div key={org.id} className="org-card active">
              <span className="org-icon">🏗️</span>
              <div className="org-info">
                <span className="org-name">{org.name}</span>
                <span className="org-description-small">{org.description}</span>
                <span className="org-badge active">✅ Active</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="org-grid coming-soon-grid">
        {comingSoonOrgs.map(org => (
          <div key={org.id} className="org-card coming-soon">
            <span className="org-icon">🚀</span>
            <div className="org-info">
              <span className="org-name">{org.name}</span>
              <span className="org-description-small">{org.description}</span>
              <span className="org-badge coming-soon">⏳ Coming Soon</span>
            </div>
          </div>
        ))}
      </div>

      <div className="org-notice">
        <span>💡</span>
        <p>
          Interested in featuring your organization? Contact us at{' '}
          <a href="mailto:partners@atelier.dev">partners@atelier.dev</a>
        </p>
      </div>
    </div>
  );
};

export default OrganizationsGrid;