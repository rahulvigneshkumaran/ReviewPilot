"use client";

import { useState } from "react";
import { api, ReviewIssue } from "@/lib/api";
import {
  ChevronDown,
  ChevronUp,
  AlertCircle,
  ShieldAlert,
  Zap,
  Sparkles,
  Check,
  Copy,
  Terminal,
  MapPin,
  Bug,
  Wrench,
} from "lucide-react";

interface IssueCardProps {
  issue: ReviewIssue;
}

export default function IssueCard({ issue }: IssueCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState<"buggy" | "fixed" | null>(null);
  const [merging, setMerging] = useState(false);
  const [mergeResult, setMergeResult] = useState<{ ok: boolean; message: string } | null>(null);

  const handleCopy = async (e: React.MouseEvent, type: "buggy" | "fixed") => {
    e.stopPropagation();
    const text = type === "buggy" ? issue.context_diff : issue.suggestion;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error("Copy failed:", err);
    }
  };

  const handleMerge = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!issue.suggestion) return;
    setMerging(true);
    setMergeResult(null);
    try {
      const result = await api.mergeIssueFix(issue.review_id, issue.id);
      setMergeResult({ ok: true, message: result.message });
    } catch (err) {
      setMergeResult({
        ok: false,
        message: err instanceof Error ? err.message : "Failed to apply fix.",
      });
    } finally {
      setMerging(false);
    }
  };

  const getIcon = () => {
    switch (issue.issue_type) {
      case "BUG":        return <Bug className="h-4 w-4 text-red-400" />;
      case "SECURITY":   return <ShieldAlert className="h-4 w-4 text-purple-400" />;
      case "PERFORMANCE":return <Zap className="h-4 w-4 text-yellow-400" />;
      case "TEST":       return <Sparkles className="h-4 w-4 text-accent" />;
      case "CODE_QUALITY": return <AlertCircle className="h-4 w-4 text-blue-400" />;
      default:           return <Terminal className="h-4 w-4 text-textSecondary" />;
    }
  };

  const getSeverityStyle = () => {
    switch (issue.severity) {
      case "CRITICAL": return "bg-red-500/10 text-red-400 border-red-500/25";
      case "HIGH":     return "bg-orange-500/10 text-orange-400 border-orange-500/25";
      case "MEDIUM":   return "bg-yellow-500/10 text-yellow-400 border-yellow-500/25";
      default:         return "bg-green-500/10 text-green-400 border-green-500/25";
    }
  };

  const getTypeStyle = () => {
    switch (issue.issue_type) {
      case "BUG":        return "bg-red-500/8 text-red-300 border-red-500/20";
      case "SECURITY":   return "bg-purple-500/8 text-purple-300 border-purple-500/20";
      case "PERFORMANCE":return "bg-yellow-500/8 text-yellow-300 border-yellow-500/20";
      case "TEST":       return "bg-accent/8 text-accent border-accent/20";
      case "CODE_QUALITY": return "bg-blue-500/8 text-blue-300 border-blue-500/20";
      default:           return "bg-border/40 text-textSecondary border-border/30";
    }
  };

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      className="glass-card rounded-xl border border-border/40 overflow-hidden cursor-pointer hover:border-border/70 transition-all"
    >
      {/* ── Header row ── */}
      <div className="p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="bg-card p-2 rounded-lg border border-border/60 flex-shrink-0">
            {getIcon()}
          </div>
          <div className="min-w-0 flex-1">
            {/* File path + line badge */}
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="font-mono text-xs font-bold text-textPrimary truncate max-w-xs sm:max-w-sm">
                {issue.file_path}
              </span>
              {/* Prominent line number badge */}
              <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/15 text-primary border border-primary/30">
                <MapPin className="h-2.5 w-2.5" />
                Line {issue.line_number}
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${getSeverityStyle()}`}>
                {issue.severity}
              </span>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border uppercase ${getTypeStyle()}`}>
                {issue.issue_type.replace("_", " ")}
              </span>
            </div>
            <p className="text-xs text-textSecondary leading-snug line-clamp-2">{issue.message}</p>
          </div>
        </div>
        <div className="flex-shrink-0">
          {expanded
            ? <ChevronUp className="h-4 w-4 text-textSecondary" />
            : <ChevronDown className="h-4 w-4 text-textSecondary" />}
        </div>
      </div>

      {/* ── Expanded body ── */}
      {expanded && (
        <div
          className="border-t border-border/30 bg-[#080D1A]/60 space-y-5 p-5"
          onClick={e => e.stopPropagation()}
        >
          {/* Full message */}
          <div>
            <h5 className="text-[10px] font-bold uppercase tracking-wider text-textSecondary mb-1.5">Issue Detail</h5>
            <p className="text-sm text-textPrimary leading-relaxed">{issue.message}</p>
          </div>

          {/* Buggy code + Fixed code side-by-side (or stacked on mobile) */}
          {(issue.context_diff || issue.suggestion) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

              {/* ── LEFT: Buggy Code ── */}
              {issue.context_diff ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h5 className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 text-red-400">
                      <Bug className="h-3 w-3" />
                      Buggy Code
                      <span className="font-mono text-[9px] bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 rounded text-red-400">
                        Line {issue.line_number}
                      </span>
                    </h5>
                    <button
                      onClick={(e) => handleCopy(e, "buggy")}
                      className="flex items-center gap-1 text-[10px] text-textSecondary hover:text-red-400 bg-card border border-border/50 px-2 py-1 rounded transition-all"
                    >
                      {copied === "buggy" ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
                      {copied === "buggy" ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <pre className="bg-red-950/20 border border-red-500/20 text-[11px] p-4 rounded-lg overflow-x-auto font-mono leading-relaxed">
                    {/* Highlight the buggy line */}
                    {issue.context_diff.split("\n").map((line, idx) => (
                      <div
                        key={idx}
                        className={
                          line.startsWith("-") || line.startsWith("+")
                            ? "text-red-400 bg-red-500/10 -mx-4 px-4"
                            : "text-textSecondary"
                        }
                      >
                        {line || "\u00a0"}
                      </div>
                    ))}
                  </pre>
                </div>
              ) : (
                <div className="flex items-center justify-center rounded-lg border border-border/20 bg-card/30 p-6">
                  <p className="text-xs text-textSecondary">No buggy code snippet available</p>
                </div>
              )}

              {/* ── RIGHT: Fixed Code ── */}
              {issue.suggestion ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h5 className="text-[10px] font-bold uppercase tracking-wider flex items-center gap-1.5 text-green-400">
                      <Wrench className="h-3 w-3" />
                      Fixed Code
                    </h5>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={(e) => handleCopy(e, "fixed")}
                        className="flex items-center gap-1 text-[10px] text-textSecondary hover:text-green-400 bg-card border border-border/50 px-2 py-1 rounded transition-all"
                      >
                        {copied === "fixed" ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
                        {copied === "fixed" ? "Copied" : "Copy"}
                      </button>
                      <button
                        onClick={handleMerge}
                        disabled={merging || mergeResult?.ok === true}
                        className={`flex items-center gap-1 text-[10px] font-semibold px-2.5 py-1 rounded transition-all border ${
                          mergeResult?.ok
                            ? "bg-green-500/10 text-green-400 border-green-500/25 cursor-default"
                            : mergeResult?.ok === false
                            ? "bg-red-500/10 text-red-400 border-red-500/20"
                            : "bg-primary hover:bg-indigo-700 text-white border-primary/20"
                        }`}
                      >
                        {merging ? (
                          <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        ) : mergeResult?.ok ? (
                          <Check className="h-3 w-3" />
                        ) : (
                          <Sparkles className="h-3 w-3" />
                        )}
                        {merging ? "Applying…" : mergeResult?.ok ? "Applied ✓" : "Merge Fix to GitHub"}
                      </button>
                    </div>
                  </div>
                  {/* Result message below the buttons */}
                  {mergeResult && (
                    <div className={`flex items-start gap-2 text-xs p-3 rounded-lg border ${
                      mergeResult.ok
                        ? "bg-green-500/10 border-green-500/25 text-green-300"
                        : "bg-red-500/10 border-red-500/25 text-red-300"
                    }`}>
                      {mergeResult.ok
                        ? <Check className="h-4 w-4 flex-shrink-0 mt-0.5 text-green-400" />
                        : <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5 text-red-400" />}
                      <span className="leading-relaxed">{mergeResult.message}</span>
                    </div>
                  )}
                  <pre className="bg-green-950/20 border border-green-500/20 text-[11px] p-4 rounded-lg overflow-x-auto font-mono leading-relaxed">
                    {issue.suggestion.split("\n").map((line, idx) => (
                      <div
                        key={idx}
                        className={
                          line.startsWith("+")
                            ? "text-green-400 bg-green-500/10 -mx-4 px-4"
                            : line.startsWith("-")
                            ? "text-red-400"
                            : line.startsWith("#") || line.startsWith("//")
                            ? "text-textSecondary/60 italic"
                            : "text-green-300"
                        }
                      >
                        {line || "\u00a0"}
                      </div>
                    ))}
                  </pre>
                </div>
              ) : (
                <div className="flex items-center justify-center rounded-lg border border-border/20 bg-card/30 p-6">
                  <p className="text-xs text-textSecondary italic">No automated fix available for this issue type.</p>
                </div>
              )}
            </div>
          )}

          {/* No code at all */}
          {!issue.context_diff && !issue.suggestion && (
            <p className="text-xs text-textSecondary italic">No code context available for this issue.</p>
          )}
        </div>
      )}
    </div>
  );
}
