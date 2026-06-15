"use client";

import { Component, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * PRODUCTION ERROR BOUNDARY
 * Catches all React rendering errors and prevents white screen
 * Shows user-friendly error UI with recovery options
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    // Log to console in development
    console.error("ErrorBoundary caught error:", error, errorInfo);
    
    // In production, you would send to error tracking service
    // Example: Sentry.captureException(error);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    // Optionally reload the page
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background flex items-center justify-center px-4">
          <div className="max-w-md w-full space-y-6 text-center">
            <div className="flex justify-center">
              <div className="p-4 rounded-full bg-red-500/10 border border-red-500/20">
                <AlertTriangle className="h-12 w-12 text-red-400" />
              </div>
            </div>
            
            <div className="space-y-2">
              <h1 className="font-outfit text-2xl font-bold text-textPrimary">
                Something went wrong
              </h1>
              <p className="text-sm text-textSecondary">
                We encountered an unexpected error. Don't worry, your data is safe.
              </p>
            </div>

            {process.env.NODE_ENV === "development" && this.state.error && (
              <div className="text-left bg-red-950/20 border border-red-500/20 rounded-lg p-4">
                <p className="text-xs font-mono text-red-300 break-all">
                  {this.state.error.toString()}
                </p>
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={this.handleReset}
                className="flex items-center justify-center gap-2 px-6 py-3 bg-primary hover:bg-indigo-700 text-white rounded-lg font-semibold transition-all"
              >
                <RefreshCw className="h-4 w-4" />
                Reload Page
              </button>
              
              <button
                onClick={() => window.location.href = "/dashboard"}
                className="px-6 py-3 bg-card border border-border hover:bg-primary/5 text-textPrimary rounded-lg font-semibold transition-all"
              >
                Go to Dashboard
              </button>
            </div>

            <p className="text-xs text-textSecondary">
              If this problem persists, please contact support or try clearing your browser cache.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
