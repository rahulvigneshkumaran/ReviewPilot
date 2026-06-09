"use client";

import { useState } from "react";
import { Settings, Save, RefreshCw, CheckCircle, Database } from "lucide-react";

export default function SettingsPage() {
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [seedStatus, setSeedStatus] = useState<"idle" | "loading" | "success">("idle");

  const [form, setForm] = useState({
    enableScans: true,
    enableComments: true,
    blockThreshold: 75,
    qdrantLimit: 3,
    webhookSecret: "reviewpilot_secret_token_12345"
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const handleSeed = () => {
    setSeedStatus("loading");
    // Simulate database seeding webhook/endpoint check
    setTimeout(() => {
      setSeedStatus("success");
      setTimeout(() => setSeedStatus("idle"), 3000);
    }, 2000);
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="font-outfit text-3xl font-bold tracking-tight">System Settings</h1>
        <p className="text-sm text-textSecondary mt-1">
          Adjust scanning thresholds, configure webhook secrets, and seed guideline standards.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Core scan configs form */}
        <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-6">
          <div className="glass-card rounded-xl p-6 space-y-6">
            <h3 className="text-lg font-semibold font-outfit text-textPrimary">Scan Configurations</h3>

            <div className="space-y-4">
              {/* Toggle switch for webhook scans */}
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <label className="text-sm font-semibold text-textPrimary">Automated scans</label>
                  <p className="text-xs text-textSecondary">Trigger review loops automatically on opened PR webhooks.</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.enableScans}
                    onChange={(e) => setForm({ ...form, enableScans: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-[#090F1E] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-textSecondary after:border-border after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary peer-checked:after:bg-white"></div>
                </label>
              </div>

              {/* Toggle switch for PR comments */}
              <div className="flex items-center justify-between gap-4 pt-4 border-t border-border/40">
                <div className="space-y-0.5">
                  <label className="text-sm font-semibold text-textPrimary">Inline PR comments</label>
                  <p className="text-xs text-textSecondary">Post findings and fix suggestions directly onto GitHub files.</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.enableComments}
                    onChange={(e) => setForm({ ...form, enableComments: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-[#090F1E] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-textSecondary after:border-border after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary peer-checked:after:bg-white"></div>
                </label>
              </div>

              {/* Block threshold input */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-border/40">
                <div className="space-y-1">
                  <label className="text-sm font-semibold text-textPrimary">Block merge risk threshold</label>
                  <p className="text-xs text-textSecondary">Block pull requests with a risk score above this value.</p>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={form.blockThreshold}
                    onChange={(e) => setForm({ ...form, blockThreshold: Number(e.target.value) })}
                    className="w-24 bg-[#090F1E] border border-border/80 rounded-lg px-3 py-2 text-sm text-textPrimary font-mono focus:outline-none focus:border-primary transition-all"
                  />
                  <span className="text-xs text-textSecondary">score (1-100)</span>
                </div>
              </div>

              {/* Qdrant rule limit input */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-border/40">
                <div className="space-y-1">
                  <label className="text-sm font-semibold text-textPrimary">RAG guidelines fetch limit</label>
                  <p className="text-xs text-textSecondary">Maximum rule standards to append to the agent context.</p>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={form.qdrantLimit}
                    onChange={(e) => setForm({ ...form, qdrantLimit: Number(e.target.value) })}
                    className="w-24 bg-[#090F1E] border border-border/80 rounded-lg px-3 py-2 text-sm text-textPrimary font-mono focus:outline-none focus:border-primary transition-all"
                  />
                  <span className="text-xs text-textSecondary">rules</span>
                </div>
              </div>
            </div>

            {/* Save trigger */}
            <div className="flex items-center justify-between gap-4 pt-4 border-t border-border/40">
              <span className="text-xs text-green-400 font-semibold flex items-center gap-1.5 h-6">
                {saveSuccess && (
                  <>
                    <CheckCircle className="h-4 w-4" />
                    Settings saved successfully!
                  </>
                )}
              </span>
              <button
                type="submit"
                className="flex items-center gap-2 rounded-lg bg-primary hover:bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white transition-all shadow-md shadow-primary/10"
              >
                <Save className="h-4 w-4" />
                Save Configurations
              </button>
            </div>
          </div>
        </form>

        {/* Database administration seed side-card */}
        <div className="lg:col-span-1 space-y-6">
          <div className="glass-card rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-semibold font-outfit text-textPrimary">Database Administration</h3>
            <p className="text-xs text-textSecondary leading-relaxed">
              If guidelines, security compliance definitions, or clean code rules are updated, run a seed to synchronize Qdrant vectors and SQL registries.
            </p>

            <button
              onClick={handleSeed}
              disabled={seedStatus === "loading"}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#090F1E] hover:bg-primary/10 border border-border/80 hover:border-primary/50 px-4 py-2.5 text-xs font-semibold text-textPrimary transition-all disabled:opacity-50"
            >
              {seedStatus === "loading" ? (
                <RefreshCw className="h-4 w-4 animate-spin text-primary" />
              ) : seedStatus === "success" ? (
                <CheckCircle className="h-4 w-4 text-green-400" />
              ) : (
                <Database className="h-4 w-4 text-accent" />
              )}
              {seedStatus === "loading"
                ? "Synchronizing guidelines..."
                : seedStatus === "success"
                ? "Guidelines synced!"
                : "Sync Guideline Rules"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
