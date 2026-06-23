import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ScrollToTop } from '../components/ui/ScrollToTop';

describe('ScrollToTop Component', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(0);
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
  });

  it('is initially hidden when scroll position is 0', () => {
    render(<ScrollToTop />);
    const button = screen.queryByTestId('scroll-to-top');
    expect(button).not.toBeInTheDocument();
  });

  it('appears when scrolled past the threshold', () => {
    render(<ScrollToTop />);

    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(350);
    window.dispatchEvent(new Event('scroll'));

    const button = screen.getByTestId('scroll-to-top');
    expect(button).toBeInTheDocument();
  });

  it('disappears when scrolled back up', () => {
    render(<ScrollToTop />);

    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(350);
    window.dispatchEvent(new Event('scroll'));
    expect(screen.getByTestId('scroll-to-top')).toBeInTheDocument();

    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(100);
    window.dispatchEvent(new Event('scroll'));
    expect(screen.queryByTestId('scroll-to-top')).not.toBeInTheDocument();
  });

  it('scrolls to top smoothly when clicked', () => {
    render(<ScrollToTop />);

    vi.spyOn(window, 'scrollY', 'get').mockReturnValue(400);
    window.dispatchEvent(new Event('scroll'));

    const button = screen.getByTestId('scroll-to-top');
    fireEvent.click(button);

    expect(window.scrollTo).toHaveBeenCalledWith({
      top: 0,
      behavior: 'smooth',
    });
  });
});
