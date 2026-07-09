import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Skeleton } from '../Skeleton';
import SkeletonContributorDashboard from './SkeletonContributorDashboard';

describe('Skeleton Framework Tests', () => {
  it('renders the base Skeleton component with default classes', () => {
    const { container } = render(<Skeleton data-testid="skeleton-base" />);
    const skeletonEl = container.firstChild as HTMLElement;
    
    expect(skeletonEl).toBeInTheDocument();
    expect(skeletonEl).toHaveClass('animate-shimmer');
    expect(skeletonEl).toHaveClass('bg-gradient-to-r');
    expect(skeletonEl).toHaveClass('rounded');
  });

  it('merges custom classes into the base Skeleton component correctly', () => {
    const { container } = render(<Skeleton className="h-6 w-36 rounded-full custom-class" />);
    const skeletonEl = container.firstChild as HTMLElement;
    
    expect(skeletonEl).toHaveClass('animate-shimmer');
    expect(skeletonEl).toHaveClass('h-6');
    expect(skeletonEl).toHaveClass('w-36');
    expect(skeletonEl).toHaveClass('rounded-full');
    expect(skeletonEl).toHaveClass('custom-class');
  });

  it('renders the SkeletonContributorDashboard without crashing', () => {
    const { container } = render(<SkeletonContributorDashboard />);
    // Verify that the dashboard wrapper is rendered
    expect(container.querySelector('.max-w-7xl')).toBeInTheDocument();
    
    // Verify that multiple skeleton primitive components are instantiated inside
    const skeletons = container.querySelectorAll('.animate-shimmer');
    expect(skeletons.length).toBeGreaterThan(10); // It has numerous placeholders
  });
});
