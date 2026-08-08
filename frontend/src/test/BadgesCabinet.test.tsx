import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import BadgesCabinet, { Badge } from '../components/BadgesCabinet';

// Mock framer-motion to prevent ESM bundle loading issue in vitest jsdom
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock BadgeTooltip to isolate BadgesCabinet logic
vi.mock('../components/BadgeTooltip', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));



const MOCK_BADGES: Badge[] = [
  {
    id: '1',
    name: 'Git Novice',
    description: 'Committed your first file',
    icon: '🌱',
    unlockCriteria: 'Make 1 commit',
    earned: true,
    earnedAt: '2026-01-01',
    module: 'Git Basics',
  },
  {
    id: '2',
    name: 'Branch Master',
    description: 'Created 5 git branches',
    icon: '🌿',
    unlockCriteria: 'Create 5 branches',
    earned: true,
    earnedAt: '2026-01-02',
    module: 'Git Basics',
  },
  {
    id: '3',
    name: 'PR Hero',
    description: 'Submitted a pull request',
    icon: '🚀',
    unlockCriteria: 'Open 1 PR',
    earned: false,
    module: 'Pull Requests',
  },
  {
    id: '4',
    name: 'Merge Wizard',
    description: 'Resolved merge conflicts',
    icon: '🧙',
    unlockCriteria: 'Resolve 3 conflicts',
    earned: false,
    module: 'Pull Requests',
  },
  {
    id: '5',
    name: 'Code Reviewer',
    description: 'Reviewed teammate PR',
    icon: '🔍',
    unlockCriteria: 'Approve 1 PR',
    earned: true,
    earnedAt: '2026-01-05',
    module: 'Pull Requests',
  },
  {
    id: '6',
    name: 'Security Champion',
    description: 'Found vulnerability in code',
    icon: '🛡️',
    unlockCriteria: 'Report 1 issue',
    earned: false,
    module: 'Security',
  },
];

describe('BadgesCabinet', () => {
  beforeEach(() => {
    // Reset state
  });

  it('renders loading state when loading prop is true', () => {
    render(<BadgesCabinet badges={[]} loading={true} />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders total badge count and earned stats correctly', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={10} />);
    expect(screen.getByText('3/6')).toBeInTheDocument();
    expect(screen.getByText('Git Novice')).toBeInTheDocument();
    expect(screen.getByText('PR Hero')).toBeInTheDocument();
  });

  it('renders earned vs locked legend', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} />);
    expect(screen.getByText('Legend:')).toBeInTheDocument();
    expect(screen.getByText('Criteria completed')).toBeInTheDocument();
    expect(screen.getByText('Unlock criteria pending')).toBeInTheDocument();
  });

  it('filters badges by search query', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={10} />);
    const searchInput = screen.getByPlaceholderText(/Search badges/i);

    fireEvent.change(searchInput, { target: { value: 'Branch' } });
    expect(screen.getByText('Branch Master')).toBeInTheDocument();
    expect(screen.queryByText('Git Novice')).not.toBeInTheDocument();
    expect(screen.queryByText('PR Hero')).not.toBeInTheDocument();
  });

  it('filters badges by earned vs locked status', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={10} />);

    // Click 'Earned' status filter button
    const earnedButton = screen.getByRole('button', { name: /Earned \(3\)/i });
    fireEvent.click(earnedButton);

    expect(screen.getByText('Git Novice')).toBeInTheDocument();
    expect(screen.getByText('Branch Master')).toBeInTheDocument();
    expect(screen.getByText('Code Reviewer')).toBeInTheDocument();
    expect(screen.queryByText('PR Hero')).not.toBeInTheDocument();
    expect(screen.queryByText('Security Champion')).not.toBeInTheDocument();
  });

  it('filters badges by module selector dropdown', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={10} />);

    const moduleSelect = screen.getByLabelText(/Filter by module/i);
    fireEvent.change(moduleSelect, { target: { value: 'Git Basics' } });

    expect(screen.getByText('Git Novice')).toBeInTheDocument();
    expect(screen.getByText('Branch Master')).toBeInTheDocument();
    expect(screen.queryByText('PR Hero')).not.toBeInTheDocument();
  });

  it('groups badges by module when group toggle is clicked', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={10} />);

    const groupButton = screen.getByRole('button', { name: /Group by Module/i });
    fireEvent.click(groupButton);

    expect(screen.getByText('Git Basics')).toBeInTheDocument();
    expect(screen.getByText('Pull Requests')).toBeInTheDocument();
    expect(screen.getByText('Security')).toBeInTheDocument();
  });

  it('paginates badges according to page size', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={2} />);

    // First page should show 2 items
    expect(screen.getByText(/Showing 1 to 2 of 6 badges/i)).toBeInTheDocument();

    // Click Next Page button
    const nextButton = screen.getByLabelText('Next page');
    fireEvent.click(nextButton);

    expect(screen.getByText(/Showing 3 to 4 of 6 badges/i)).toBeInTheDocument();
  });

  it('displays empty state and resets filters when search query has no matches', () => {
    render(<BadgesCabinet badges={MOCK_BADGES} pageSize={10} />);

    const searchInput = screen.getByPlaceholderText(/Search badges/i);
    fireEvent.change(searchInput, { target: { value: 'nonexistent badge' } });

    expect(screen.getByText('No badges match your criteria')).toBeInTheDocument();

    const resetButton = screen.getByRole('button', { name: /Reset All Filters/i });
    fireEvent.click(resetButton);

    expect(screen.getByText('Git Novice')).toBeInTheDocument();
  });
});
