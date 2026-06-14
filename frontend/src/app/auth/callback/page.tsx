"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { CheckCircle, AlertCircle, Loader2 } from "lucide-react";

/**
 * OAuth callback page — receives the JWT token from the backend redirect
 * after GitHub OAuth authorization completes.
 *
 * URL format: /auth/callback?token=<JWT>&username=<github_user>&avatar=<url>
 */
function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");

    if (!token) {
      setStatus("error");
      setErrorMsg(
        "No authentication token received from GitHub. Please try logging in again."
      );
      return;
    }

    // Store JWT in localStorage (same key used by auth-context and api.ts)
    localStorage.setItem("access_token", token);
    setStatus("success");

    // Redirect to dashboard after a brief moment so the user sees the success state
    const timer = setTimeout(() => {
      router.replace("/dashboard");
    }, 1200);

    return () => clearTimeout(timer);
  }, [searchParams, router]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 py-12">
      {/* Decorative blur highlights matching login page */}
      <div className="absolute top-1/4 left-1/4 h-72 w-72 rounded-full bg-primary/20 blur-[100px] animate-pulse-slow" />
      <div className="absolute bottom-1/4 right-1/4 h-80 w-80 rounded-full bg-secondary/15 blur-[120px] animate-pulse-slow" />

      <div className="w-full max-w-md space-y-8 z-10">
        {/* Branding */}
        <div className="text-center">
          <h1 className="font-outfit text-4xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-primary via-secondary to-accent bg-clip-text text-transparent">
              ReviewPilot
            </span>
          </h1>
        </div>

        {/* Status card */}
        <div className="glass-card rounded-2xl p-8 shadow-2xl text-center space-y-4">
          {status === "loading" && (
            <>
              <Loader2 className="h-10 w-10 text-primary mx-auto animate-spin" />
              <p className="text-sm text-textSecondary font-medium">
                Completing GitHub authentication…
              </p>
            </>
          )}

          {status === "success" && (
            <>
              <CheckCircle className="h-10 w-10 text-green-400 mx-auto" />
              <p className="text-sm text-textPrimary font-semibold">
                GitHub connected successfully!
              </p>
              <p className="text-xs text-textSecondary">
                Redirecting to dashboard…
              </p>
            </>
          )}

          {status === "error" && (
            <>
              <AlertCircle className="h-10 w-10 text-red-400 mx-auto" />
              <p className="text-sm text-red-400 font-semibold">
                Authentication failed
              </p>
              <p className="text-xs text-textSecondary">{errorMsg}</p>
              <button
                onClick={() => router.push("/login")}
                className="mt-2 inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-secondary px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                Back to Login
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/** Wrap in Suspense because useSearchParams() requires it in Next.js App Router */
export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background">
          <Loader2 className="h-8 w-8 text-primary animate-spin" />
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
