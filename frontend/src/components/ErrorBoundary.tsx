import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Project Ouroboros Uncaught UI Error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-2xl mx-auto font-mono text-xs my-12 bg-zinc-950 border border-rose-900/80 rounded-2xl p-6 shadow-2xl space-y-4 animate-fade-in text-zinc-200">
          <div className="flex items-center gap-3 text-rose-400 border-b border-rose-950 pb-3">
            <AlertTriangle className="w-6 h-6 shrink-0" />
            <div>
              <h2 className="text-sm font-bold text-zinc-100">
                {this.props.fallbackTitle || 'Component Render Error Intercepted'}
              </h2>
              <p className="text-[11px] text-zinc-400">
                Project Ouroboros Fault Isolation Guardrail prevented a blank screen.
              </p>
            </div>
          </div>

          <div className="bg-zinc-900/80 p-3 rounded-lg border border-zinc-800 text-rose-300 font-mono text-[11px] overflow-x-auto leading-relaxed">
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </div>

          {this.state.errorInfo?.componentStack && (
            <details className="text-[10px] text-zinc-500">
              <summary className="cursor-pointer hover:text-zinc-300 transition">View Component Stack</summary>
              <pre className="mt-2 p-2 bg-black/60 rounded border border-zinc-900 overflow-x-auto max-h-40 leading-normal">
                {this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}

          <div className="flex gap-2 pt-2">
            <button
              onClick={this.handleReset}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold transition shadow-lg shadow-emerald-500/20"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reload & Recover</span>
            </button>
            <button
              onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
              className="px-3 py-2 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 transition"
            >
              Dismiss
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
