"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  FolderKanban,
  GitPullRequest,
  ShieldAlert,
  BarChart3,
  History,
  Settings,
  LogOut,
  Code
} from "lucide-react";

export default function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();

  const navItems = [
    { name: "Repositories", href: "/dashboard", icon: FolderKanban },
    { name: "PR Reviews", href: "/dashboard/reviews", icon: GitPullRequest },
    { name: "Security Insights", href: "/dashboard/security", icon: ShieldAlert },
    { name: "Risk Analytics", href: "/dashboard/analytics", icon: BarChart3 },
    { name: "Review History", href: "/dashboard/history", icon: History },
    { name: "Settings", href: "/dashboard/settings", icon: Settings },
  ];

  return (
    <aside className="w-64 bg-card border-r border-border/50 flex flex-col min-h-screen text-textPrimary">
      {/* Branding */}
      <div className="h-16 flex items-center gap-3 px-6 border-b border-border/50">
        <div className="bg-primary/20 p-1.5 rounded-lg border border-primary/30">
          <Code className="h-5 w-5 text-primary" />
        </div>
        <span className="font-outfit text-xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          ReviewPilot
        </span>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 px-4 py-6 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? "bg-primary text-white shadow-lg shadow-primary/25"
                  : "text-textSecondary hover:bg-border/30 hover:text-textPrimary"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Logout Actions */}
      <div className="p-4 border-t border-border/50">
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-red-400 hover:bg-red-500/10 transition-all"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}
