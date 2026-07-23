import { NavLink } from "react-router-dom";
import {
  LayoutGrid,
  BookOpen,
  TerminalSquare,
  MessageSquare,
  Settings,
} from "lucide-react";

export function MobileBottomNav() {
  const navItems = [
    { to: "/dashboard", label: "Home", icon: LayoutGrid },
    { to: "/learning-path", label: "Learn", icon: BookOpen },
    { to: "/contributor-sandbox", label: "Sandbox", icon: TerminalSquare },
    { to: "/chat", label: "Chat", icon: MessageSquare },
    { to: "/profile", label: "Profile", icon: Settings },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t-4 border-black bg-white pb-safe lg:hidden dark:border-[#2e2924] dark:bg-[#0f0e0c]">
      <div className="flex h-16 items-center justify-around px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [
                  "flex flex-col items-center justify-center gap-0.5 rounded-xl px-2.5 py-1.5 transition-all duration-200 border-2 border-transparent text-xs font-bold",
                  isActive
                    ? "bg-[#C3C0FF]/25 border-black dark:border-[#2e2924] text-text dark:text-[#f0ebe2] shadow-card-sm"
                    : "text-muted hover:text-text dark:text-[#c4bbae] dark:hover:text-[#f0ebe2]",
                ].join(" ")
              }
            >
              <Icon size={18} />
              <span className="text-[10px] tracking-tight">{item.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}

export default MobileBottomNav;
