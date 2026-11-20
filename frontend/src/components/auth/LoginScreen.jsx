import { useState } from "react";
import { Lock, Mail, AlertCircle, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/authStore";

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Completá tu correo electrónico y contraseña.");
      return;
    }
    setSubmitting(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        "No se pudo iniciar sesión. Verificá tu conexión y credenciales.";
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f4f5f7] flex flex-col justify-center items-center px-4">
      <div className="w-full max-w-md bg-white border border-gray-200 rounded-xl shadow-sm p-8">
        <div className="flex items-center gap-2.5 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[#ff6600] flex items-center justify-center text-white font-bold text-base">
            V
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 tracking-tight leading-none">
              VektorTerminal
            </h1>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Plataforma de Análisis Fundamental & Gestión Patrimonial
            </p>
          </div>
        </div>

        <hr className="my-5 border-gray-100" />

        <h2 className="text-base font-semibold text-gray-900 mb-1">
          Iniciar sesión
        </h2>
        <p className="text-xs text-gray-500 mb-5">
          Ingresá con tus credenciales asignadas para acceder a la terminal.
        </p>

        {error && (
          <div className="mb-4 flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg p-3">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="login-email"
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Correo electrónico
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@dominio.com"
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="login-password"
              className="block text-xs font-medium text-gray-700 mb-1"
            >
              Contraseña
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 px-4 bg-[#ff6600] hover:bg-[#e55a00] disabled:opacity-60 text-white text-sm font-semibold rounded-lg transition-colors cursor-pointer"
          >
            {submitting ? "Verificando acceso..." : "Ingresar a la Terminal"}
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-gray-100 flex items-center gap-2 text-[11px] text-gray-400">
          <ShieldCheck className="w-4 h-4 text-gray-400 shrink-0" />
          <span>
            Acceso protegido por roles (Superadmin, Asesor y Cliente).
          </span>
        </div>
      </div>
    </div>
  );
}