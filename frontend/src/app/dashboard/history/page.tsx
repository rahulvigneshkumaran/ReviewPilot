"use client";

import { useState, useEffect } from "react";
import { api, ReviewData } from "@/lib/api";
import Link from "next/link";
import { History, Search, Calendar, CheckCircle, AlertTriangle, ArrowUpRight } from "lucide-react";

export default function HistoryPage() {
  const [reviews, setReviews] = useState<ReviewData[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadHistory() {
      try {
        const data = await api.getReviews();
        setReviews(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadHistory();
  }, []);

  // Format dates
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  // Filter reviews based on search query
  const filteredReviews = reviews.filter(
    (rev) =>
      rev.pr_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rev.repo_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getSeverityStyle = (severity?: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      case "HIGH":
        return "bg-orange-500/10 text-orange-400 border-orange-500/20";
      case "MEDIUM":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
      default:
        return "bg-green-500/10 text-green-400 border-green-500/20";
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="font-outfit text-3xl font-bold tracking-tight">Review History</h1>
        <p className="text-sm text-textSecondary mt-1">
          Access records of all previous pull request scans and risk configurations.
        </p>
      </div>

      {/* Filter and search controls bar */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
        <div className="relative w-full sm:max-w-xs">
          <input
            type="text"
            placeholder="Search by title or repository..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-card border border-border/80 rounded-lg pl-10 pr-4 py-2 text-sm text-textPrimary placeholder-textSecondary focus:outline-none focus:border-primary transition-all"
          />
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-textSecondary" />
        </div>
      </div>

      {/* Review History Table list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
        </div>
      ) : filteredReviews.length === 0 ? (
        <div className="text-center py-16 bg-card border border-border/40 rounded-xl space-y-3">
          <History className="h-12 w-12 text-textSecondary mx-auto opacity-40" />
          <p className="text-sm text-textSecondary">No previous reviews found matching your search query.</p>
        </div>
      ) : (
        <div className="glass-card rounded-xl border border-border/40 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#090F1E] border-b border-border/50 text-textSecondary uppercase font-semibold">
                  <th className="px-6 py-4">Repository</th>
                  <th className="px-6 py-4">Pull Request</th>
                  <th className="px-6 py-4">Scan Date</th>
                  <th className="px-6 py-4 text-center">Score</th>
                  <th className="px-6 py-4 text-center">Severity</th>
                  <th className="px-6 py-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {filteredReviews.map((rev) => (
                  <tr key={rev.id} className="hover:bg-card/40 transition-all font-medium">
                    <td className="px-6 py-4 text-textSecondary font-semibold">{rev.repo_name}</td>
                    <td className="px-6 py-4">
                      <div className="font-bold text-textPrimary leading-tight">#{rev.pr_number}</div>
                      <div className="text-[10px] text-textSecondary mt-0.5 line-clamp-1">{rev.pr_title}</div>
                    </td>
                    <td className="px-6 py-4 text-textSecondary flex items-center gap-1.5 mt-1">
                      <Calendar className="h-3.5 w-3.5" />
                      {formatDate(rev.started_at)}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <code className="bg-[#090F1E] px-2 py-0.5 rounded border border-border/40 font-bold text-accent">
                        {rev.risk_score !== undefined ? rev.risk_score : "-"}
                      </code>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${getSeverityStyle(rev.severity)}`}>
                        {rev.severity || "LOW"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <Link
                        href="/dashboard/reviews"
                        className="inline-flex items-center gap-1.5 bg-[#090F1E] hover:bg-primary/10 border border-border/80 hover:border-primary/50 text-[10px] font-semibold text-textSecondary hover:text-primary px-3 py-1.5 rounded-lg transition-all"
                      >
                        Details
                        <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
