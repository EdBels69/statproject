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
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4" role="alert" aria-live="assertive">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
            <div className="flex items-center justify-center mb-6">
              <div className="bg-red-100 rounded-full p-3">
                <ExclamationTriangleIcon className="h-8 w-8 text-red-600" aria-hidden="true" />
              </div>
            </div>
            
            <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
              Something went wrong
            </h1>
            <p className="text-gray-600 text-center mb-6">
              An unexpected error occurred while processing your analysis. We apologize for the inconvenience.
            </p>

            {this.state.error && (
              <details className="mb-6">
                <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700 select-none">
                  View error details
                </summary>
                <div className="mt-2 p-3 bg-gray-50 rounded text-xs font-mono text-red-600 overflow-auto max-h-32">
                  {this.state.error.toString()}
                  {this.state.errorInfo && this.state.errorInfo.componentStack}
                </div>
              </details>
            )}

            <div className="space-y-3">
              <button
                onClick={this.handleReset}
                className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-colors font-medium"
              >
                Return to Home
              </button>
              <button
                onClick={() => window.location.reload()}
                className="w-full px-4 py-2 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors font-medium"
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
