"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import Sidebar from "@/components/Sidebar";
import { RefreshCw, User } from "lucide-react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, loading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, loading, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex min-h-screen bg-background text-textPrimary">
      {/* Sidebar navigation panel */}
      <Sidebar />

      {/* Main Page scroll wrap */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {/* Top Header navbar */}
        <header className="h-16 border-b border-border/50 bg-card/45 backdrop-blur-md px-8 flex items-center justify-between z-40">
          <div>
            <h2 className="text-xs font-semibold text-textSecondary uppercase tracking-wider">ReviewPilot Console</h2>
          </div>

          <div className="flex items-center gap-6">
            {/* Sync status */}
            <span className="flex items-center gap-1.5 text-xs text-green-400 font-medium">
              <span className="h-2 w-2 rounded-full bg-green-400 animate-ping"></span>
              Live Synced
            </span>

            {/* Profile actions */}
            <div className="flex items-center gap-3">
              {user?.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt="GitHub Profile Avatar"
                  className="h-8 w-8 rounded-full border border-border"
                />
              ) : (
                <div className="bg-border p-1.5 rounded-full">
                  <User className="h-4 w-4 text-textSecondary" />
                </div>
              )}
              <span className="text-sm font-semibold text-textPrimary">{user?.github_username}</span>
            </div>
          </div>
        </header>

        {/* Dynamic page contents body */}
        <main className="flex-1 overflow-y-auto px-8 py-8 relative">
          <div className="absolute top-0 right-1/4 h-64 w-64 rounded-full bg-primary/5 blur-[80px] pointer-events-none"></div>
          <div className="max-w-6xl mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
