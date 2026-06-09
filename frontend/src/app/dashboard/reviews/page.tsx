"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, ReviewData } from "@/lib/api";
import RiskMeter from "@/components/RiskMeter";
import IssueCard from "@/components/IssueCard";
import { GitPullRequest, Calendar, MessageSquare, AlertTriangle, FileCode, RefreshCw } from "lucide-react";

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<ReviewData[]>([]);
  const [selectedReview, setSelectedReview] = useState<ReviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const loadReviews = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const data = await api.getReviews();
      setReviews(data);
      // Keep selected review in sync
      setSelectedReview((prev) => {
        if (!prev) return data.length > 0 ? data[0] : null;
        const updated = data.find((r) => r.id === prev.id);
        return updated ?? prev;
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  // Poll every 5s while any review is PENDING or RUNNING
  useEffect(() => {
    const hasPending = reviews.some((r) => r.status === "PENDING" || r.status === "RUNNING");
    if (hasPending) {
      pollingRef.current = setInterval(() => loadReviews(true), 5000);
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [reviews, loadReviews]);

  // Format dates
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "bg-green-500/10 text-green-400 border-green-500/25";
      case "RUNNING":
        return "bg-primary/10 text-primary border-primary/25 animate-pulse";
      case "FAILED":
        return "bg-red-500/10 text-red-400 border-red-500/25";
      default:
        return "bg-textSecondary/10 text-textSecondary border-border";
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-outfit text-3xl font-bold tracking-tight">Pull Request Reviews</h1>
          <p className="text-sm text-textSecondary mt-1">
            Explore and audit review feedback, risk metrics, and generated unit test coverages.
          </p>
        </div>
        <button
          onClick={() => loadReviews(true)}
          disabled={refreshing || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 hover:border-primary/50 bg-card hover:bg-primary/5 text-sm text-textSecondary hover:text-textPrimary font-medium transition-all disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
        </div>
      ) : reviews.length === 0 ? (
        <div className="text-center py-16 bg-card border border-border/40 rounded-xl space-y-3">
          <GitPullRequest className="h-12 w-12 text-textSecondary mx-auto opacity-40" />
          <p className="text-sm text-textSecondary">No reviews found yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          {/* Left panel: Reviews sidebar list */}
          <div className="space-y-4 lg:col-span-1">
            <h3 className="text-xs font-bold uppercase tracking-wider text-textSecondary px-2">Recent Scans</h3>
            <div className="space-y-3">
              {reviews.map((rev) => (
                <div
                  key={rev.id}
                  onClick={() => setSelectedReview(rev)}
                  className={`glass-card rounded-xl p-4 cursor-pointer text-left transition-all ${
                    selectedReview?.id === rev.id
                      ? "border-primary/60 bg-primary/5 shadow-md shadow-primary/5"
                      : "border-border/40"
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-semibold text-textSecondary truncate">{rev.repo_name}</span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase ${getStatusStyle(rev.status)}`}>
                        {rev.status === "PENDING" || rev.status === "RUNNING" ? (
                          <span className="flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-current inline-block animate-pulse" />
                            {rev.status}
                          </span>
                        ) : rev.status}
                      </span>
                    </div>
                    <h4 className="text-xs font-bold text-textPrimary leading-snug line-clamp-1">
                      #{rev.pr_number} - {rev.pr_title}
                    </h4>
                    <div className="flex items-center justify-between text-[10px] text-textSecondary font-medium pt-1">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(rev.started_at)}
                      </span>
                      {rev.risk_score !== undefined && (
                        <span className="font-semibold text-textPrimary">
                          Risk: <code className="bg-[#090F1E] px-1.5 py-0.5 rounded border border-border/40 text-accent font-bold">{rev.risk_score}</code>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right panel: Review details page */}
          {selectedReview && (
            <div className="lg:col-span-2 space-y-6">
              {/* Detail Header card */}
              <div className="glass-card rounded-xl p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <GitPullRequest className="h-6 w-6 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2.5">
                      <h2 className="font-outfit text-xl font-bold text-textPrimary leading-snug">
                        #{selectedReview.pr_number} - {selectedReview.pr_title}
                      </h2>
                    </div>
                    <p className="text-xs text-textSecondary mt-0.5">
                      Repository: <code className="bg-[#090F1E] px-1.5 py-0.5 rounded border border-border/40 text-textPrimary font-semibold">{selectedReview.repo_name}</code>
                    </p>
                  </div>
                </div>
              </div>

              {/* Score summary breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
                {/* Risk Gauge */}
                <div className="md:col-span-1 flex flex-col justify-between">
                  <RiskMeter score={selectedReview.risk_score || 0} />
                </div>

                {/* AI Markdown Report Card */}
                <div className="md:col-span-2 glass-card rounded-xl p-6 space-y-4 flex flex-col justify-between">
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-textSecondary">AI Review Summary</h4>
                    <div className="text-xs text-textSecondary space-y-3 leading-relaxed whitespace-pre-line border-t border-border/40 pt-3">
                      {selectedReview.summary || "No review summary details provided."}
                    </div>
                  </div>
                </div>
              </div>

              {/* Code Issues checklist */}
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-border/50 pb-2">
                  <h4 className="font-outfit text-lg font-bold text-textPrimary">Code Findings ({selectedReview.issues?.length || 0})</h4>
                  <span className="text-[10px] text-textSecondary">Expand items to apply suggested fixes</span>
                </div>

                <div className="space-y-3">
                  {selectedReview.issues && selectedReview.issues.length > 0 ? (
                    selectedReview.issues.map((issue) => (
                      <IssueCard key={issue.id} issue={issue} />
                    ))
                  ) : (
                    <div className="text-center py-10 bg-card border border-border/40 rounded-xl">
                      <p className="text-xs text-textSecondary">No specific code findings recorded for this pull request.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
