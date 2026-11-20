import { useEffect, useState } from "react";
import {
  Users,
  UserPlus,
  X,
  Shield,
  CheckCircle2,
  Ban,
  KeyRound,
  AlertCircle,
} from "lucide-react";
import apiClient from "../../api/client";
import { useAuth } from "../../context/authStore";

const ROLE_LABELS = {
  superadmin: {
    label: "Superadmin",
    badge: "bg-purple-100 text-purple-800 border-purple-200",
  },
  advisor: {
    label: "Asesor",
    badge: "bg-orange-100 text-orange-800 border-orange-200",
  },
  client: {
    label: "Cliente",
    badge: "bg-blue-100 text-blue-800 border-blue-200",
  },
};

export default function UserManagementModal({ isOpen, onClose }) {
  const { user: currentUser, isSuperAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  // Formulario de alta (solo superadmin)
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("client");
  const [advisorId, setAdvisorId] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiClient.get("/admin/users");
      setUsers(res.data?.users || []);
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo cargar la lista de usuarios."
      );
    } finally {
      setLoading(false);
    }
  };

useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;

    const loadUsers = async () => {
      setLoading(true);
      setError("");
      try {
        const res = await apiClient.get("/admin/users");
        if (!cancelled) {
          setUsers(res.data?.users || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err?.response?.data?.detail ||
              "No se pudo cargar la lista de usuarios."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadUsers();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const advisors = users.filter(
    (u) => (u.role === "advisor" || u.role === "superadmin") && u.is_active
  );

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    setFeedback("");
    setCreating(true);
    try {
      await apiClient.post("/admin/users", {
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        role,
        advisor_id: role === "client" && advisorId ? Number(advisorId) : null,
        must_change_password: true,
      });
      setFullName("");
      setEmail("");
      setPassword("");
      setRole("client");
      setAdvisorId("");
      setFeedback("Usuario creado correctamente.");
      await fetchUsers();
    } catch (err) {
      setError(err?.response?.data?.detail || "Error al crear el usuario.");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (target) => {
    setError("");
    setFeedback("");
    try {
      await apiClient.patch(`/admin/users/${target.id}`, {
        is_active: !target.is_active,
      });
      setFeedback(
        `Usuario ${target.email} ${!target.is_active ? "activado" : "desactivado"}.`
      );
      await fetchUsers();
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo actualizar el estado."
      );
    }
  };

  const handleResetPassword = async (target) => {
    const newPass = window.prompt(
      `Ingresá una contraseña temporal (mín. 8 caracteres) para ${target.email}:`
    );
    if (!newPass) return;
    setError("");
    setFeedback("");
    try {
      await apiClient.patch(`/admin/users/${target.id}`, {
        reset_password: newPass,
      });
      setFeedback(
        `Contraseña reseteada para ${target.email} (se le pedirá cambiarla al ingresar).`
      );
    } catch (err) {
      setError(
        err?.response?.data?.detail || "No se pudo resetear la contraseña."
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center p-4">
      <div className="bg-white border border-gray-200 rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-[#ff6600]" />
            <div>
              <h3 className="text-base font-bold text-gray-900">
                {isSuperAdmin
                  ? "Administración de Usuarios y Roles"
                  : "Mis Clientes Asignados"}
              </h3>
              <p className="text-xs text-gray-500">
                {isSuperAdmin
                  ? "Creá asesores o clientes, asigná carteras y controlá accesos."
                  : "Clientes vinculados a tu cuenta de asesor."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-6">
          {error && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg p-3">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {feedback && (
            <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-lg p-3">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{feedback}</span>
            </div>
          )}

          {isSuperAdmin && (
            <form
              onSubmit={handleCreate}
              className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3"
            >
              <div className="flex items-center gap-1.5 text-xs font-bold text-gray-800 uppercase tracking-wide">
                <UserPlus className="w-4 h-4 text-[#ff6600]" />
                <span>Alta de nuevo usuario</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                <input
                  type="text"
                  placeholder="Nombre completo"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  className="px-3 py-2 text-xs bg-white text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="px-3 py-2 text-xs bg-white text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
                />
                <input
                  type="password"
                  placeholder="Clave inicial (mín. 8)"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="px-3 py-2 text-xs bg-white text-gray-900 placeholder:text-gray-400 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
                />
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="px-3 py-2 text-xs bg-white text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
                >
                  <option value="client">Rol: Cliente</option>
                  <option value="advisor">Rol: Asesor</option>
                  <option value="superadmin">Rol: Superadmin</option>
                </select>

                {role === "client" ? (
                  <select
                    value={advisorId}
                    onChange={(e) => setAdvisorId(e.target.value)}
                    className="px-3 py-2 text-xs bg-white text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:border-[#ff6600]"
                  >
                    <option value="">Sin asesor asignado</option>
                    {advisors.map((adv) => (
                      <option key={adv.id} value={adv.id}>
                        Asesor: {adv.full_name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="px-3 py-2 text-[11px] text-gray-500 flex items-center">
                    No requiere asesor
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 text-xs font-semibold bg-[#ff6600] hover:bg-[#e55a00] text-white rounded-lg disabled:opacity-60 cursor-pointer"
                >
                  {creating ? "Creando..." : "Crear usuario"}
                </button>
              </div>
            </form>
          )}

          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-[11px] font-semibold uppercase text-gray-500">
                  <th className="py-2.5 px-3">Usuario</th>
                  <th className="py-2.5 px-3">Rol</th>
                  <th className="py-2.5 px-3">Asesor asignado</th>
                  <th className="py-2.5 px-3">Estado</th>
                  {isSuperAdmin && (
                    <th className="py-2.5 px-3 text-right">Acciones</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {loading ? (
                  <tr>
                    <td
                      colSpan={isSuperAdmin ? 5 : 4}
                      className="py-6 text-center text-gray-400"
                    >
                      Cargando usuarios...
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td
                      colSpan={isSuperAdmin ? 5 : 4}
                      className="py-6 text-center text-gray-400"
                    >
                      No hay usuarios para mostrar.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => {
                    const roleInfo =
                      ROLE_LABELS[u.role] || ROLE_LABELS.client;
                    const isSelf = u.id === currentUser?.id;
                    return (
                      <tr key={u.id} className="hover:bg-gray-50/70">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-gray-900">
                            {u.full_name}{" "}
                            {isSelf && (
                              <span className="text-[10px] text-gray-400 font-normal">
                                (Vos)
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-gray-500">
                            {u.email}
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${roleInfo.badge}`}
                          >
                            <Shield className="w-3 h-3" />
                            {roleInfo.label}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-gray-600">
                          {u.advisor_name || "-"}
                        </td>
                        <td className="py-2.5 px-3">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Activo
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-red-600 font-medium">
                              <Ban className="w-3.5 h-3.5" />
                              Inactivo
                            </span>
                          )}
                        </td>
                        {isSuperAdmin && (
                          <td className="py-2.5 px-3 text-right space-x-2">
                            <button
                              type="button"
                              onClick={() => handleResetPassword(u)}
                              title="Resetear contraseña"
                              className="inline-flex items-center gap-1 px-2 py-1 text-[11px] border border-gray-200 rounded hover:bg-gray-100 text-gray-700 cursor-pointer"
                            >
                              <KeyRound className="w-3 h-3" />
                              Clave
                            </button>
                            {!isSelf && (
                              <button
                                type="button"
                                onClick={() => handleToggleActive(u)}
                                className={`px-2 py-1 text-[11px] rounded border cursor-pointer ${
                                  u.is_active
                                    ? "border-red-200 text-red-600 hover:bg-red-50"
                                    : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                                }`}
                              >
                                {u.is_active ? "Desactivar" : "Activar"}
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}