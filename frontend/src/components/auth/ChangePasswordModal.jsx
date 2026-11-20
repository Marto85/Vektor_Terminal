import { useState } from "react";
import { KeyRound, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { useAuth } from "../../context/authStore";

export default function ChangePasswordModal({ isOpen, onClose, forced = false }) {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  if (!isOpen && !forced) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (newPassword.trim().length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("La confirmación no coincide con la nueva contraseña.");
      return;
    }

    setLoading(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess("Contraseña actualizada correctamente.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      if (onClose) {
        setTimeout(() => {
          setSuccess("");
          onClose();
        }, 800);
      }
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo actualizar la contraseña."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white border border-gray-200 rounded-xl shadow-lg w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-[#ff6600]" />
            <h3 className="text-sm font-bold text-gray-900">
              {forced
                ? "Cambio de contraseña obligatorio"
                : "Cambiar contraseña"}
            </h3>
          </div>
          {!forced && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <p className="text-xs text-gray-500 mb-4">
          {forced
            ? "Por seguridad, debés definir una contraseña personal de al menos 8 caracteres antes de continuar."
            : "Ingresá tu contraseña actual y definí una nueva clave de al menos 8 caracteres."}
        </p>

        {error && (
          <div className="mb-3 flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg p-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-3 flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg p-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Contraseña actual
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Nueva contraseña (mín. 8 caracteres)
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Confirmar nueva contraseña
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-white text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
              required
            />
          </div>

          <div className="pt-2 flex justify-end gap-2">
            {!forced && onClose && (
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-lg cursor-pointer"
              >
                Cancelar
              </button>
            )}
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-xs font-semibold bg-[#ff6600] hover:bg-[#e55a00] text-white rounded-lg disabled:opacity-60 cursor-pointer"
            >
              {loading ? "Guardando..." : "Actualizar contraseña"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}