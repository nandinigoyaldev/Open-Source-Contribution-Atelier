import { Outlet, useLocation } from "react-router-dom";

export function PublicLayout() {
  const { pathname } = useLocation();
  // These routes already render their own main landmark (LoginPage or AuthPageShell).
  const hasMain =
    pathname === "/" ||
    pathname === "/login" ||
    pathname === "/signup" ||
    pathname === "/verify-notice" ||
    pathname.startsWith("/verify-email/");

  return hasMain ? (
    <Outlet />
  ) : (
    <main id="main-content" tabIndex={-1}>
      <Outlet />
    </main>
  );
}
