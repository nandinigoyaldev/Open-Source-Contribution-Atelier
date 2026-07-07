/**
 * Middleware for route protection and caching.
 * 
 * @file middleware.ts
 * @location frontend/middleware.ts
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

// Protected routes
const protectedRoutes = ['/dashboard', '/profile', '/settings', '/admin'];

// Public routes that should be cached
const cacheableRoutes = ['/', '/about', '/learn'];

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const token = await getToken({ req: request });
  
  // Check if route is protected
  if (protectedRoutes.some((route) => pathname.startsWith(route))) {
    if (!token) {
      const url = new URL('/login', request.url);
      url.searchParams.set('callbackUrl', pathname);
      return NextResponse.redirect(url);
    }
  }
  
  // Cache static pages
  if (cacheableRoutes.some((route) => pathname === route)) {
    const response = NextResponse.next();
    response.headers.set('Cache-Control', 'public, max-age=3600, stale-while-revalidate=86400');
    return response;
  }
  
  return NextResponse.next();
}

// Configure middleware matcher
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder (public assets)
     */
    '/((?!_next/static|_next/image|favicon.ico|public/).*)',
  ],
};