import { Component } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorMessage: "" };
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      errorMessage: error?.message || "Error inesperado en la interfaz.",
    };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary capturó un error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.compact) {
        return (
          <div className="bg-white border border-amber-200 rounded-xl p-8 text-center space-y-3 shadow-sm my-4">
            <div className="w-10 h-10 rounded-full bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h2 className="text-sm font-bold text-gray-900">
              No se pudo renderizar esta sección
            </h2>
            <p className="text-xs text-gray-500 max-w-md mx-auto">
              {this.state.errorMessage}
            </p>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, errorMessage: "" })}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reintentar vista
            </button>
          </div>
        );
      }

      return (
        <div className="min-h-screen bg-[#1e1e1e] text-gray-200 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-[#262626] border border-gray-700 rounded-xl p-6 text-center space-y-4 shadow-xl">
            <div className="w-11 h-11 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h1 className="text-base font-bold text-white">
              Ocurrió un error al renderizar la vista
            </h1>
            <p className="text-xs text-gray-400 leading-relaxed">
              {this.state.errorMessage}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Recargar terminal
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
