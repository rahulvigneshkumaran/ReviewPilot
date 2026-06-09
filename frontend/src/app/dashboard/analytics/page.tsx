"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell
} from "recharts";
import { GitPullRequest, Code, ShieldAlert, BadgeAlert, FileCode2, CheckCircle2 } from "lucide-react";

export default function AnalyticsPage() {
  // Mock statistics matching requirements
  const stats = [
    { name: "PRs Reviewed", value: "128", change: "+12% vs last month", icon: GitPullRequest, color: "text-primary bg-primary/10 border-primary/20" },
    { name: "Issues Detected", value: "342", change: "+5% vs last month", icon: Code, color: "text-yellow-500 bg-yellow-500/10 border-yellow-500/20" },
    { name: "Security Findings", value: "48", change: "-15% vs last month", icon: ShieldAlert, color: "text-purple-500 bg-purple-500/10 border-purple-500/20" },
    { name: "Average Risk Score", value: "32", change: "-8% vs last month", icon: BadgeAlert, color: "text-accent bg-accent/10 border-accent/20" },
    { name: "Generated Test Cases", value: "186", change: "+24% vs last month", icon: FileCode2, color: "text-green-500 bg-green-500/10 border-green-500/20" },
    { name: "Fix Acceptance Rate", value: "88%", change: "+2% vs last month", icon: CheckCircle2, color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
  ];

  // Mock charts dataset
  const riskHistory = [
    { date: "May 29", risk: 42 },
    { date: "Jun 01", risk: 38 },
    { date: "Jun 03", risk: 55 },
    { date: "Jun 05", risk: 29 },
    { date: "Jun 07", risk: 48 },
    { date: "Jun 08", risk: 32 },
  ];

  const issueCategories = [
    { name: "Bugs", value: 92, color: "#EF4444" },        // Red
    { name: "Security", value: 48, color: "#A855F7" },    // Purple
    { name: "Performance", value: 64, color: "#EAB308" }, // Yellow
    { name: "Quality", value: 112, color: "#3B82F6" },    // Blue
    { name: "Tests", value: 26, color: "#10B981" },       // Green
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="font-outfit text-3xl font-bold tracking-tight">Risk Analytics</h1>
        <p className="text-sm text-textSecondary mt-1">
          Explore scanning analytics, fix validation ratios, and security defect spreads.
        </p>
      </div>

      {/* Stats Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.name} className="glass-card rounded-xl p-6 flex flex-col justify-between space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-textSecondary uppercase tracking-wider">{stat.name}</span>
                <div className={`p-2 rounded-lg border ${stat.color}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
              <div>
                <h3 className="font-outfit text-3xl font-extrabold text-textPrimary leading-none">{stat.value}</h3>
                <span className="text-[10px] text-green-400 font-semibold mt-2 inline-block">{stat.change}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recharts Diagrams Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Risk Score history AreaChart */}
        <div className="lg:col-span-2 glass-card rounded-xl p-6 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-textSecondary">Average Risk Score Trend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={riskHistory}>
                <defs>
                  <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#4F46E5" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748B" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "#111827", borderColor: "#1E293B", color: "#F8FAFC", fontSize: 11 }}
                />
                <Area type="monotone" dataKey="risk" stroke="#4F46E5" strokeWidth={2} fillOpacity={1} fill="url(#colorRisk)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Issue distribution PieChart */}
        <div className="lg:col-span-1 glass-card rounded-xl p-6 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-textSecondary">Defects Breakdown</h3>
          <div className="h-48 relative flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={issueCategories}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {issueCategories.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "#111827", borderColor: "#1E293B", color: "#F8FAFC", fontSize: 11 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          {/* Custom Legends list */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            {issueCategories.map((cat) => (
              <div key={cat.name} className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: cat.color }}></span>
                <span className="text-textSecondary font-medium">{cat.name}:</span>
                <span className="text-textPrimary font-semibold">{cat.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
