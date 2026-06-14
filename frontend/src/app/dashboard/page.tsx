"use client";

import { useState, useEffect, useCallback } from "react";
import {
  api,
  RepositoryData,
  BranchData,
  PullRequestData,
} from "@/lib/api";
import {
  FolderKanban,
  Plus,
  CheckCircle,
  XCircle,
  GitBranch,
  GitPullRequest,
  ChevronDown,
  ChevronRight,
  Loader2,
  ExternalLink,
  FileCode2,
  AlertCircle,
  Play,
  KeyRound,
  Github,
  LogIn,
} from "lucide-react";

interface RepoExpansion {
  branches: BranchData[];
  pullRequests: PullRequestData[];
  loadingBranches: boolean;
  loadingPRs: boolean;
  errorBranches?: string;
  errorPRs?: string;
}

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<RepositoryData[]>([]);
  const [newRepoName, setNewRepoName] = useState("");
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [expandedRepoId, setExpandedRepoId] = useState<string | null>(null);
  const [expansions, setExpansions] = useState<Record<string, RepoExpansion>>({});
  const [triggeringPR, setTriggeringPR] = useState<string | null>(null);
  const [triggerMsg, setTriggerMsg] = useState<Record<string, string>>({});
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showPatLogin, setShowPatLogin] = useState(false);
  const [showConnectForm, setShowConnectForm] = useState(false);
  const [patValue, setPatValue] = useState("");
  const [patLoading, setPatLoading] = useState(false);
  const [patError, setPatError] = useState<string | null>(null);

  useEffect(() => {
    // Check if we have a real JWT token
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    setIsAuthenticated(!!token);

    async function loadRepos() {
      try {
        const data = await api.getRepositories();
        setRepos(data);
        // Show connect form by default only when no repos exist yet
        setShowConnectForm(data.length === 0);
      } catch (err) {
        console.error(err);
        setShowConnectForm(true);
      } finally {
        setLoading(false);
      }
    }
    loadRepos();
  }, []);

  const handlePatLogin = async () => {
    if (!patValue.trim()) return;
    setPatLoading(true);
    setPatError(null);
    try {
      // Use env var for production URL — never hardcode localhost
      const baseUrl =
        process.env.NEXT_PUBLIC_API_URL ??
        "https://reviewpilot-hvrp.onrender.com/api/v1";
      const endpoint = `${baseUrl}/auth/dev-login`;
      console.log("[PAT Login] POST", endpoint);

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_token: patValue.trim() }),
      });

      // Log status so the real failure reason is visible in DevTools
      console.log("[PAT Login] response status:", res.status, res.statusText);

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        console.error("[PAT Login] error body:", errBody);
        throw new Error(
          (errBody as { detail?: string }).detail ||
            `Server error ${res.status}: ${res.statusText}`
        );
      }
      const data = (await res.json()) as { access_token: string };
      localStorage.setItem("access_token", data.access_token);
      setIsAuthenticated(true);
      setShowPatLogin(false);
      setPatValue("");
      // Reload repos with real data
      const freshRepos = await api.getRepositories();
      setRepos(freshRepos);
      setShowConnectForm(freshRepos.length === 0);
      // Clear all cached expansions so real data loads fresh on next expand
      setExpansions({});
      setExpandedRepoId(null);
    } catch (err: unknown) {
      console.error("[PAT Login] caught error:", err);
      setPatError(
        err instanceof Error ? err.message : "Login failed — check console for details"
      );
    } finally {
      setPatLoading(false);
    }
  };

  // A real connected repo has a UUID id (e.g. "550e8400-e29b-..."); mock fallback repos use "repo-1" etc.
  const isMockRepo = (id: string) =>
    !id.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);

  const loadRepoDetails = useCallback(async (repo: RepositoryData) => {
    // If this is a mock/fallback repo (not authenticated), don't attempt API calls
    if (isMockRepo(repo.id)) {
      setExpansions((prev) => ({
        ...prev,
        [repo.id]: {
          branches: [],
          pullRequests: [],
          loadingBranches: false,
          loadingPRs: false,
          errorBranches: "auth_required",
          errorPRs: "auth_required",
        },
      }));
      return;
    }

    // Set initial loading state
    setExpansions((prev) => ({
      ...prev,
      [repo.id]: {
        branches: prev[repo.id]?.branches ?? [],
        pullRequests: prev[repo.id]?.pullRequests ?? [],
        loadingBranches: true,
        loadingPRs: true,
      },
    }));

    // Fetch branches and PRs in parallel
    const [branchResult, prResult] = await Promise.allSettled([
      api.getBranches(repo.id),
      api.getPullRequests(repo.id, "open"),
    ]);

    setExpansions((prev) => ({
      ...prev,
      [repo.id]: {
        branches:
          branchResult.status === "fulfilled" ? branchResult.value : [],
        pullRequests:
          prResult.status === "fulfilled" ? prResult.value : [],
        loadingBranches: false,
        loadingPRs: false,
        errorBranches:
          branchResult.status === "rejected"
            ? "Could not load branches"
            : undefined,
        errorPRs:
          prResult.status === "rejected"
            ? "Could not load pull requests"
            : undefined,
      },
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToggleExpand = useCallback(
    (repo: RepositoryData) => {
      if (expandedRepoId === repo.id) {
        setExpandedRepoId(null);
      } else {
        setExpandedRepoId(repo.id);
        if (!expansions[repo.id]) {
          loadRepoDetails(repo);
        }
      }
    },
    [expandedRepoId, expansions, loadRepoDetails]
  );

  const handleToggle = async (id: string, currentStatus: boolean) => {
    try {
      const updatedStatus = !currentStatus;
      setRepos(repos.map((r) => (r.id === id ? { ...r, is_active: updatedStatus } : r)));
      await api.toggleRepository(id, updatedStatus);
    } catch {
      setRepos(repos.map((r) => (r.id === id ? { ...r, is_active: currentStatus } : r)));
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoName.trim()) return;
    setConnectError(null);
    setIsSubmitting(true);
    try {
      const newRepo = await api.connectRepository(newRepoName.trim());
      setRepos([newRepo, ...repos]);
      setNewRepoName("");
      setShowConnectForm(false);
    } catch (err: unknown) {
      setConnectError(
        err instanceof Error ? err.message : "Failed to connect repository."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTriggerReview = async (repoId: string, pr: PullRequestData) => {
    const key = `${repoId}-${pr.number}`;
    setTriggeringPR(key);
    try {
      const result = await api.triggerReview(repoId, pr.number);
      setTriggerMsg((prev) => ({
        ...prev,
        [key]: result.message || "Review queued! Check the Reviews tab for results.",
      }));
    } catch (err: unknown) {
      setTriggerMsg((prev) => ({
        ...prev,
        [key]: err instanceof Error ? err.message : "Failed to trigger review.",
      }));
    } finally {
      setTriggeringPR(null);
      setTimeout(() => {
        setTriggerMsg((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }, 5000);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Title Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-outfit text-3xl font-bold tracking-tight">
            Connected Repositories
          </h1>
          <p className="text-sm text-textSecondary mt-1">
            Connect repositories to set up automated GitHub pull request
            scanning. Click a repo to view its branches and open PRs.
          </p>
        </div>
        {!isAuthenticated && (
          <button
            onClick={() => setShowPatLogin((v) => !v)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-xs font-semibold hover:bg-green-500/20 transition-all"
          >
            <Github className="h-4 w-4" />
            Connect GitHub Account
          </button>
        )}
        {isAuthenticated && (
          <span className="flex items-center gap-1.5 text-xs text-green-400 font-medium">
            <CheckCircle className="h-4 w-4" />
            GitHub Connected
          </span>
        )}
      </div>

      {/* GitHub PAT Login Panel */}
      {showPatLogin && !isAuthenticated && (
        <div className="glass-card rounded-xl p-6 border border-green-500/20 bg-green-500/5 space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10 border border-green-500/20">
              <KeyRound className="h-5 w-5 text-green-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-textPrimary">GitHub Personal Access Token (PAT) Login</h3>
              <p className="text-xs text-textSecondary mt-0.5">
                Create a PAT at <span className="text-green-400">github.com → Settings → Developer settings → Personal access tokens</span> with <code className="bg-[#090F1E] px-1 rounded border border-border/40">repo</code> scope.
              </p>
            </div>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="password"
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              value={patValue}
              onChange={(e) => setPatValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handlePatLogin()}
              className="flex-1 bg-[#090F1E] border border-border/80 rounded-lg px-4 py-2.5 text-sm text-textPrimary placeholder-textSecondary focus:outline-none focus:border-green-500 transition-all font-mono"
            />
            <button
              onClick={handlePatLogin}
              disabled={patLoading || !patValue.trim()}
              className="flex items-center justify-center gap-2 rounded-lg bg-green-600 hover:bg-green-700 px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
            >
              {patLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
              {patLoading ? "Logging in..." : "Login"}
            </button>
          </div>
          {patError && (
            <p className="text-xs text-red-400 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" />
              {patError}
            </p>
          )}
        </div>
      )}

      {/* Connect New Repository Form */}
      {showConnectForm ? (
        <div className="glass-card rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold font-outfit text-textPrimary">
              Connect a repository
            </h3>
            {repos.length > 0 && (
              <button
                onClick={() => setShowConnectForm(false)}
                className="text-xs text-textSecondary hover:text-textPrimary transition-colors"
              >
                Cancel
              </button>
            )}
          </div>
          <form onSubmit={handleConnect} className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="owner/repo  or  https://github.com/owner/repo"
              value={newRepoName}
              onChange={(e) => setNewRepoName(e.target.value)}
              disabled={isSubmitting}
              className="flex-1 bg-[#090F1E] border border-border/80 rounded-lg px-4 py-2.5 text-sm text-textPrimary placeholder-textSecondary focus:outline-none focus:border-primary transition-all"
            />
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center justify-center gap-2 rounded-lg bg-primary hover:bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50"
            >
              {isSubmitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Connect Repo
            </button>
          </form>
          {connectError && (
            <div className="mt-3 flex items-start gap-2 text-xs">
              <AlertCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 flex-shrink-0" />
              <div>
                <span className="text-red-400">{connectError}</span>
                {!isAuthenticated && (
                  <span className="text-textSecondary ml-1.5">
                    —{" "}
                    <button
                      onClick={() => setShowPatLogin(true)}
                      className="text-green-400 underline hover:no-underline"
                    >
                      Login with GitHub PAT
                    </button>{" "}
                    to connect real repositories.
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        <button
          onClick={() => setShowConnectForm(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-border/50 hover:border-primary/50 bg-card hover:bg-primary/5 text-sm text-textSecondary hover:text-textPrimary font-medium transition-all"
        >
          <Plus className="h-4 w-4" />
          Connect another repository
        </button>
      )}

      {/* Repositories List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : repos.length === 0 ? (
        <div className="text-center py-16 bg-card border border-border/40 rounded-xl space-y-3">
          <FolderKanban className="h-12 w-12 text-textSecondary mx-auto opacity-40" />
          <p className="text-sm text-textSecondary">No repositories connected yet.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {repos.map((repo) => {
            const isExpanded = expandedRepoId === repo.id;
            const exp = expansions[repo.id];

            return (
              <div
                key={repo.id}
                className="glass-card rounded-xl overflow-hidden"
              >
                {/* Repo Header Row */}
                <div className="p-5 flex items-center gap-4">
                  {/* Expand toggle */}
                  <button
                    onClick={() => handleToggleExpand(repo)}
                    className="flex-shrink-0 text-textSecondary hover:text-primary transition-colors"
                    aria-label="Toggle details"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5" />
                    ) : (
                      <ChevronRight className="h-5 w-5" />
                    )}
                  </button>

                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-3 flex-wrap">
                      <span className="font-outfit text-base font-bold text-textPrimary break-all">
                        {repo.full_name}
                      </span>
                      <span
                        className={`flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
                          repo.is_active
                            ? "bg-green-500/10 text-green-400"
                            : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {repo.is_active ? (
                          <CheckCircle className="h-3 w-3" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        {repo.is_active ? "Active" : "Paused"}
                      </span>
                    </div>
                    {repo.description && (
                      <p className="text-xs text-textSecondary leading-relaxed line-clamp-1">
                        {repo.description}
                      </p>
                    )}
                    <div className="flex items-center gap-3 text-[10px] text-textSecondary font-medium">
                      <span className="flex items-center gap-1">
                        <GitBranch className="h-3 w-3" />
                        default:{" "}
                        <code className="bg-[#090F1E] px-1.5 py-0.5 rounded border border-border/40">
                          {repo.default_branch}
                        </code>
                      </span>
                      {exp && !exp.loadingBranches && (
                        <span className="flex items-center gap-1 text-textSecondary">
                          <GitBranch className="h-3 w-3" />
                          {exp.branches.length} branches
                        </span>
                      )}
                      {exp && !exp.loadingPRs && (
                        <span className="flex items-center gap-1 text-textSecondary">
                          <GitPullRequest className="h-3 w-3" />
                          {exp.pullRequests.length} open PRs
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Webhook toggle */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-textSecondary font-medium hidden sm:block">
                      Webhook scans
                    </span>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={repo.is_active}
                        onChange={() => handleToggle(repo.id, repo.is_active)}
                        className="sr-only peer"
                      />
                      <div className="w-10 h-5 bg-[#090F1E] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-textSecondary after:border-border after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary peer-checked:after:bg-white" />
                    </label>
                  </div>
                </div>

                {/* Expanded Detail Panel */}
                {isExpanded && (
                  <div className="border-t border-border/40 bg-[#080D1A]/60">
                    <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-border/40">
                      {/* ── Branches Panel ── */}
                      <div className="p-5 space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-textSecondary flex items-center gap-2">
                            <GitBranch className="h-3.5 w-3.5 text-primary" />
                            Branches
                          </h4>
                          {!isMockRepo(repo.id) && (
                            <button
                              onClick={() => loadRepoDetails(repo)}
                              className="text-[10px] text-textSecondary hover:text-primary transition-colors flex items-center gap-1"
                              title="Refresh branches and PRs"
                            >
                              <Loader2 className={`h-3 w-3 ${exp?.loadingBranches || exp?.loadingPRs ? "animate-spin" : ""}`} />
                              Refresh
                            </button>
                          )}
                        </div>

                        {exp?.errorBranches === "auth_required" ? (
                          <div className="flex flex-col gap-3 py-3">
                            <p className="text-xs text-textSecondary flex items-center gap-1.5">
                              <AlertCircle className="h-3.5 w-3.5 text-yellow-400 flex-shrink-0" />
                              Login with your GitHub account to view real branches.
                            </p>
                            <button
                              onClick={() => { setShowPatLogin(true); setShowConnectForm(false); }}
                              className="flex items-center gap-1.5 text-[10px] font-semibold px-3 py-1.5 rounded-md bg-green-500/10 hover:bg-green-500/20 text-green-400 border border-green-500/25 transition-all w-fit"
                            >
                              <KeyRound className="h-3 w-3" />
                              Login with GitHub PAT
                            </button>
                          </div>
                        ) : exp?.loadingBranches ? (
                          <div className="flex items-center gap-2 text-xs text-textSecondary py-4">
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                            Fetching branches from GitHub…
                          </div>
                        ) : exp?.branches.length === 0 ? (
                          <p className="text-xs text-textSecondary py-3">
                            No branches found. Make sure you are authenticated with a real GitHub token.
                          </p>
                        ) : (
                          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                            {exp?.branches.map((branch) => (
                              <div
                                key={branch.name}
                                className="flex items-center justify-between gap-2 py-1.5 px-3 rounded-lg bg-[#090F1E] border border-border/30"
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <GitBranch className="h-3 w-3 text-textSecondary flex-shrink-0" />
                                  <code className="text-xs text-textPrimary font-medium truncate">
                                    {branch.name}
                                  </code>
                                  {branch.is_default && (
                                    <span className="text-[9px] bg-primary/15 text-primary border border-primary/30 px-1.5 py-0.5 rounded font-semibold">
                                      default
                                    </span>
                                  )}
                                  {branch.protected && (
                                    <span className="text-[9px] bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 px-1.5 py-0.5 rounded font-semibold">
                                      protected
                                    </span>
                                  )}
                                </div>
                                <code className="text-[10px] text-textSecondary font-mono flex-shrink-0">
                                  {branch.sha.slice(0, 7)}
                                </code>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* ── Open Pull Requests Panel ── */}
                      <div className="p-5 space-y-3">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-textSecondary flex items-center gap-2">
                          <GitPullRequest className="h-3.5 w-3.5 text-accent" />
                          Open Pull Requests
                        </h4>

                        {exp?.errorPRs === "auth_required" ? (
                          <div className="py-3">
                            <p className="text-xs text-textSecondary flex items-center gap-1.5">
                              <AlertCircle className="h-3.5 w-3.5 text-yellow-400 flex-shrink-0" />
                              Login with your GitHub account to view open pull requests.
                            </p>
                          </div>
                        ) : exp?.loadingPRs ? (
                          <div className="flex items-center gap-2 text-xs text-textSecondary py-4">
                            <Loader2 className="h-4 w-4 animate-spin text-accent" />
                            Fetching pull requests from GitHub…
                          </div>
                        ) : exp?.pullRequests.length === 0 ? (
                          <p className="text-xs text-textSecondary py-3">
                            No open pull requests on this repository.
                          </p>
                        ) : (
                          <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                            {exp?.pullRequests.map((pr) => {
                              const key = `${repo.id}-${pr.number}`;
                              const isTriggering = triggeringPR === key;
                              const successMsg = triggerMsg[key];

                              return (
                                <div
                                  key={pr.number}
                                  className="rounded-lg bg-[#090F1E] border border-border/30 p-3 space-y-2"
                                >
                                  {/* PR title row */}
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-1.5 flex-wrap">
                                        {pr.draft && (
                                          <span className="text-[9px] bg-gray-500/15 text-gray-400 border border-gray-500/20 px-1.5 py-0.5 rounded font-semibold">
                                            DRAFT
                                          </span>
                                        )}
                                        <span className="text-xs font-bold text-textPrimary leading-snug">
                                          #{pr.number}{" "}
                                          <span className="font-medium">{pr.title}</span>
                                        </span>
                                      </div>
                                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                                        <span className="flex items-center gap-1 text-[10px] text-textSecondary">
                                          <GitBranch className="h-3 w-3" />
                                          <code className="text-primary">{pr.head_branch}</code>
                                          <span>→</span>
                                          <code>{pr.base_branch}</code>
                                        </span>
                                        <span className="text-[10px] text-textSecondary">
                                          by{" "}
                                          <span className="text-textPrimary font-medium">
                                            {pr.author}
                                          </span>
                                        </span>
                                      </div>
                                    </div>
                                    <a
                                      href={pr.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="flex-shrink-0 text-textSecondary hover:text-primary transition-colors"
                                      title="Open on GitHub"
                                    >
                                      <ExternalLink className="h-3.5 w-3.5" />
                                    </a>
                                  </div>

                                  {/* Files changed */}
                                  {pr.changed_files !== undefined && (
                                    <div className="flex items-center gap-3 text-[10px] text-textSecondary">
                                      <span className="flex items-center gap-1">
                                        <FileCode2 className="h-3 w-3" />
                                        {pr.changed_files} files changed
                                      </span>
                                      {pr.additions !== undefined && (
                                        <span className="text-green-400 font-mono">
                                          +{pr.additions}
                                        </span>
                                      )}
                                      {pr.deletions !== undefined && (
                                        <span className="text-red-400 font-mono">
                                          -{pr.deletions}
                                        </span>
                                      )}
                                    </div>
                                  )}

                                  {/* Trigger review button */}
                                  {successMsg ? (
                                    <p className={`text-[10px] flex items-center gap-1.5 ${successMsg.toLowerCase().includes("fail") || successMsg.toLowerCase().includes("error") ? "text-red-400" : "text-green-400"}`}>
                                      <CheckCircle className="h-3 w-3 flex-shrink-0" />
                                      {successMsg}
                                    </p>
                                  ) : (
                                    <button
                                      onClick={() => handleTriggerReview(repo.id, pr)}
                                      disabled={isTriggering}
                                      className="flex items-center gap-1.5 text-[10px] font-semibold px-3 py-1.5 rounded-md bg-accent/15 hover:bg-accent/25 text-accent border border-accent/25 transition-all disabled:opacity-60"
                                    >
                                      {isTriggering ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                      ) : (
                                        <Play className="h-3 w-3" />
                                      )}
                                      {isTriggering ? "Queueing review…" : "Trigger AI Review"}
                                    </button>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
