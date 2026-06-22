import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResponsiveTable } from '../components/ui/ResponsiveTable';

describe('ResponsiveTable Component', () => {
  const columns = [
    { header: 'ID', accessor: 'id' as const, label: 'Identifier' },
    { header: 'Name', accessor: 'name' as const },
    { header: 'Role', accessor: (item: any) => <span data-testid="role">{item.role}</span> },
  ];

  const data = [
    { id: 1, name: 'Alice', role: 'Admin' },
    { id: 2, name: 'Bob', role: 'User' },
  ];

  it('renders both desktop table and mobile card layouts', () => {
    const { container } = render(
      <ResponsiveTable
        columns={columns}
        data={data}
        keyExtractor={(item) => item.id.toString()}
      />
    );

    // Desktop table should be present
    const table = container.querySelector('table');
    expect(table).toBeInTheDocument();
    
    // Check if headers are rendered in desktop
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();

    // Mobile layout should be present (hidden via sm:hidden class)
    // The mobile view has the label 'Identifier'
    const mobileLabels = screen.getAllByText('Identifier');
    expect(mobileLabels.length).toBe(2);

    // Custom accessor rendering
    const roles = screen.getAllByTestId('role');
    // 2 in desktop, 2 in mobile = 4 total
    expect(roles.length).toBe(4);
  });

  it('renders empty message when no data is provided', () => {
    const { container } = render(
      <ResponsiveTable
        columns={columns}
        data={[]}
        keyExtractor={(item: any) => item.id.toString()}
        emptyMessage="No records found"
      />
    );

    const emptyMessages = screen.getAllByText('No records found');
    // One in desktop table, one in mobile view
    expect(emptyMessages.length).toBe(2);
  });
});
