import { Component } from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

class AnalysisErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[color:var(--bg-secondary)] flex items-center justify-center p-4" role="alert" aria-live="assertive">
          <div className="max-w-md w-full bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-8">
            <div className="flex items-center justify-center mb-6">
              <div className="bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] p-3">
                <ExclamationTriangleIcon className="h-8 w-8 text-[color:var(--error)]" aria-hidden="true" />
              </div>
            </div>
            
            <h1 className="text-2xl font-bold text-[color:var(--text-primary)] text-center mb-2">
              Something went wrong
            </h1>
            <p className="text-[color:var(--text-muted)] text-center mb-6">
              An unexpected error occurred while processing your analysis. We apologize for the inconvenience.
            </p>

            {this.state.error && (
              <details className="mb-6">
                <summary className="cursor-pointer text-sm text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] select-none">
                  View error details
                </summary>
                <div className="mt-2 p-3 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] text-xs font-mono text-[color:var(--error)] overflow-auto max-h-32">
                  {this.state.error.toString()}
                  {this.state.errorInfo && this.state.errorInfo.componentStack}
                </div>
              </details>
            )}

            <div className="space-y-3">
              <button
                onClick={this.handleReset}
                className="w-full px-4 py-2 bg-[color:var(--accent)] text-[color:var(--white)] rounded-[2px] hover:opacity-90 focus:outline-none transition-colors font-medium"
                type="button"
              >
                Return to Home
              </button>
              <button
                onClick={() => window.location.reload()}
                className="w-full px-4 py-2 bg-[color:var(--white)] text-[color:var(--text-secondary)] border border-[color:var(--border-color)] rounded-[2px] hover:bg-[color:var(--bg-secondary)] focus:outline-none transition-colors font-medium"
                type="button"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default AnalysisErrorBoundary;
