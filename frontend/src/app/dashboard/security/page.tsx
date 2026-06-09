"use client";

import { useState, useEffect } from "react";
import { api, ReviewIssue, ReviewData } from "@/lib/api";
import IssueCard from "@/components/IssueCard";
import { ShieldAlert, ShieldCheck, Lock, AlertTriangle, AlertCircle } from "lucide-react";

export default function SecurityInsightsPage() {
  const [securityIssues, setSecurityIssues] = useState<ReviewIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState({ total: 0, critical: 0, high: 0, medium: 0 });

  useEffect(() => {
    async function loadSecurity() {
      try {
        const reviews = await api.getReviews();
        // Collect all security issues from all reviews
        const issues: ReviewIssue[] = [];
        reviews.forEach(rev => {
          if (rev.issues) {
            rev.issues.forEach(iss => {
              if (iss.issue_type === "SECURITY") {
                issues.push(iss);
              }
            });
          }
        });

        // Compute metrics
        const total = issues.length;
        const critical = issues.filter(iss => iss.severity === "CRITICAL").length;
        const high = issues.filter(iss => iss.severity === "HIGH").length;
        const medium = issues.filter(iss => iss.severity === "MEDIUM").length;

        setSecurityIssues(issues);
        setMetrics({ total, critical, high, medium });
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadSecurity();
  }, []);

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="font-outfit text-3xl font-bold tracking-tight">Security Insights</h1>
        <p className="text-sm text-textSecondary mt-1">
          Review aggregated security concerns, OWASP Top 10 vulnerabilities, and credentials safety.
        </p>
      </div>

      {/* Security Metrics summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="glass-card rounded-xl p-5 border-l-4 border-l-purple-500">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-textSecondary uppercase">Vulnerabilities Found</span>
            <Lock className="h-5 w-5 text-purple-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-outfit text-3xl font-bold text-textPrimary">{metrics.total}</span>
            <span className="text-xs text-textSecondary">active issues</span>
          </div>
        </div>

        <div className="glass-card rounded-xl p-5 border-l-4 border-l-red-500">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-textSecondary uppercase">Critical Issues</span>
            <AlertCircle className="h-5 w-5 text-red-500 animate-pulse" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-outfit text-3xl font-bold text-textPrimary">{metrics.critical}</span>
            <span className="text-xs text-textSecondary">severe threats</span>
          </div>
        </div>

        <div className="glass-card rounded-xl p-5 border-l-4 border-l-orange-500">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-textSecondary uppercase">High Issues</span>
            <AlertTriangle className="h-5 w-5 text-orange-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-outfit text-3xl font-bold text-textPrimary">{metrics.high}</span>
            <span className="text-xs text-textSecondary">high priority</span>
          </div>
        </div>

        <div className="glass-card rounded-xl p-5 border-l-4 border-l-yellow-500">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-textSecondary uppercase">Medium Issues</span>
            <ShieldAlert className="h-5 w-5 text-yellow-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-outfit text-3xl font-bold text-textPrimary">{metrics.medium}</span>
            <span className="text-xs text-textSecondary">medium risk</span>
          </div>
        </div>
      </div>

      {/* Audit List section */}
      <div className="space-y-4">
        <div className="border-b border-border/50 pb-2 flex items-center justify-between">
          <h3 className="font-outfit text-xl font-bold text-textPrimary">Security Findings List</h3>
          <span className="text-xs text-textSecondary font-semibold">OWASP violations & hardcoded secrets</span>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
          </div>
        ) : securityIssues.length === 0 ? (
          <div className="text-center py-16 bg-card border border-border/40 rounded-xl space-y-3">
            <ShieldCheck className="h-12 w-12 text-green-400 mx-auto opacity-70" />
            <p className="text-sm text-textSecondary">No active security concerns identified. Excellent work!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {securityIssues.map((issue) => (
              <IssueCard key={issue.id} issue={issue} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
