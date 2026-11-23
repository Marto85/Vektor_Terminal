import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Lock,
  Mail,
  ShieldCheck,
  User,
  UserCheck,
  UserPlus,
} from "lucide-react";
import apiClient from "../../api/client";
import { useAuth } from "../../context/authStore";
import BrandLogo from "../BrandLogo";

function GoogleIcon() {
  return (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M12 10.2v3.9h5.4c-.2 1.3-1.5 3.9-5.4 3.9-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.7 3.4 14.6 2.5 12 2.5 6.8 2.5 2.5 6.8 2.5 12s4.3 9.5 9.5 9.5c5.5 0 9.1-3.8 9.1-9.2 0-.6-.1-1.1-.2-1.6H12z"
      />
      <path
        fill="#34A853"
        d="M3.6 7.5l3.2 2.3C7.7 7.7 9.7 6 12 6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.7 3.4 14.6 2.5 12 2.5 8.3 2.5 5.1 4.6 3.6 7.5z"
      />
      <path
        fill="#FBBC05"
        d="M12 21.5c2.5 0 4.7-.8 6.3-2.3l-2.9-2.4c-.8.6-1.9 1-3.4 1-2.6 0-4.8-1.7-5.6-4.1l-3.2 2.5c1.5 3.1 4.7 5.3 8.8 5.3z"
      />
      <path
        fill="#4285F4"
        d="M21.1 12.3c0-.6-.1-1.1-.2-1.6H12v3.9h5.4c-.3 1.4-1.1 2.5-2.2 3.2l2.9 2.4c1.7-1.6 3-4 3-7.9z"
      />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg
      className="w-4 h-4 shrink-0 fill-current"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      />
    </svg>
  );
}

export default function LoginScreen() {
  const {
    login,
    registerPublic,
    requestRecovery,
    resetPasswordWithToken,
    startOAuthLogin,
    oauthError,
    clearOauthError,
    pendingResetToken,
  } = useAuth();

  // "login" | "register" | "recover"
  const [mode, setMode] = useState(() =>
    pendingResetToken ? "recover" : "login"
  );

  // Estado Login
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);

  // Estado Registro
  const [regUsername, setRegUsername] = useState("");
  const [regFullName, setRegFullName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regAdvisorId, setRegAdvisorId] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPassword, setRegConfirmPassword] = useState("");

  // Estado Recuperación
  const [recEmail, setRecEmail] = useState("");
  const [recToken, setRecToken] = useState(() => pendingResetToken || "");
  const [recNewPassword, setRecNewPassword] = useState("");
  const [recStep, setRecStep] = useState(() =>
    pendingResetToken ? "reset" : "request"
  );

  // Proveedores OAuth y ejecutivos disponibles en backend
  const [providers, setProviders] = useState({ google: false, github: false });
  const [advisors, setAdvisors] = useState([]);

  // Feedback
  const [submitting, setSubmitting] = useState(false);
  const [oauthLoading, setOauthLoading] = useState("");
  const [errorMsg, setErrorMsg] = useState(() => oauthError || "");
  const [infoMsg, setInfoMsg] = useState("");

  useEffect(() => {
    let active = true;
    const req = apiClient?.get?.("/auth/providers");
    if (req && typeof req.then === "function") {
      req
        .then((res) => {
          if (active && res?.data) {
            setProviders({
              google: Boolean(res.data.google),
              github: Boolean(res.data.github),
            });
          }
        })
        .catch(() => {});
    }

    const advReq = apiClient?.get?.("/auth/advisors");
    if (advReq && typeof advReq.then === "function") {
      advReq
        .then((res) => {
          if (active && Array.isArray(res?.data?.advisors)) {
            setAdvisors(res.data.advisors);
          }
        })
        .catch(() => {});
    }

    return () => {
      active = false;
    };
  }, []);

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setErrorMsg("");
    setInfoMsg("");
    clearOauthError();
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setInfoMsg("");
    if (!identifier.trim() || !password) {
      setErrorMsg("Completá tu correo electrónico y contraseña.");
      return;
    }
    setSubmitting(true);
    try {
      await login(identifier.trim(), password);
    } catch (err) {
      setErrorMsg(
        err?.response?.data?.detail ||
          "No se pudo iniciar sesión. Verificá tus credenciales."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setInfoMsg("");
    if (
      !regUsername.trim() ||
      !regFullName.trim() ||
      !regEmail.trim() ||
      !regPassword
    ) {
      setErrorMsg("Completá todos los campos obligatorios para crear tu cuenta.");
      return;
    }
    if (regPassword.length < 8) {
      setErrorMsg("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (regPassword !== regConfirmPassword) {
      setErrorMsg("Las contraseñas no coinciden.");
      return;
    }
    setSubmitting(true);
    try {
      await registerPublic({
        username: regUsername.trim().toLowerCase(),
        full_name: regFullName.trim(),
        email: regEmail.trim(),
        password: regPassword,
        advisor_id: regAdvisorId ? Number(regAdvisorId) : null,
      });
    } catch (err) {
      setErrorMsg(
        err?.response?.data?.detail || "No se pudo completar el registro."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRequestRecovery = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setInfoMsg("");
    if (!recEmail.trim()) {
      setErrorMsg("Ingresá el correo electrónico asociado a tu cuenta.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await requestRecovery(recEmail.trim());
      const extra = res?.dev_hint ? ` (${res.dev_hint})` : "";
      setInfoMsg((res?.message || "Revisá tu correo.") + extra);
      setRecStep("reset");
    } catch (err) {
      setErrorMsg(
        err?.response?.data?.detail || "No se pudo procesar la solicitud."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmReset = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    setInfoMsg("");
    if (!recToken.trim() || !recNewPassword) {
      setErrorMsg("Ingresá el código recibido por correo y la nueva contraseña.");
      return;
    }
    if (recNewPassword.length < 8) {
      setErrorMsg("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    setSubmitting(true);
    try {
      await resetPasswordWithToken(recToken.trim(), recNewPassword);
    } catch (err) {
      setErrorMsg(
        err?.response?.data?.detail ||
          "No se pudo restablecer la contraseña. Verificá el código."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleOAuthClick = async (provider) => {
    setErrorMsg("");
    setInfoMsg("");
    setOauthLoading(provider);
    try {
      await startOAuthLogin(provider);
    } catch (err) {
      setErrorMsg(
        err?.response?.data?.detail ||
          `No se pudo iniciar la autenticación con ${provider}.`
      );
      setOauthLoading("");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl p-6 sm:p-8">
        <div className="flex flex-col items-center text-center mb-6">
          <BrandLogo className="w-11 h-11 mb-3" />
          <h1 className="text-xl font-bold tracking-tight text-slate-100">
            VektorTerminal
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Plataforma de Análisis Fundamental & Gestión de Carteras
          </p>
        </div>

        {/* Selector de pestañas Ingresar / Crear cuenta */}
        {mode !== "recover" && (
          <div className="grid grid-cols-2 gap-1 bg-slate-950/90 border border-slate-800 rounded-xl p-1 mb-5">
            <button
              type="button"
              onClick={() => switchMode("login")}
              className={`py-2 text-xs font-semibold rounded-lg transition-colors ${
                mode === "login"
                  ? "bg-emerald-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Ingresar
            </button>
            <button
              type="button"
              onClick={() => switchMode("register")}
              className={`py-2 text-xs font-semibold rounded-lg transition-colors ${
                mode === "register"
                  ? "bg-emerald-600 text-white shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Crear cuenta
            </button>
          </div>
        )}

        {errorMsg && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-rose-500/40 bg-rose-950/50 px-3.5 py-2.5 text-xs text-rose-200">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {infoMsg && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-emerald-500/40 bg-emerald-950/50 px-3.5 py-2.5 text-xs text-emerald-200">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>{infoMsg}</span>
          </div>
        )}

        {/* MODO 1: INGRESAR */}
        {mode === "login" && (
          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="login-identifier"
                className="block text-xs font-medium text-slate-300 mb-1.5"
              >
                Usuario o correo electrónico
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="login-identifier"
                  type="text"
                  autoComplete="username"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="usuario o nombre@dominio.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="login-password"
                  className="block text-xs font-medium text-slate-300"
                >
                  Contraseña
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setRecStep("request");
                    switchMode("recover");
                  }}
                  className="text-[11px] text-emerald-400 hover:text-emerald-300"
                >
                  ¿Olvidaste tu usuario o clave?
                </button>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="login-password"
                  type={showPass ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-10 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPass((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  tabIndex={-1}
                >
                  {showPass ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-colors cursor-pointer"
            >
              {submitting ? "Verificando..." : "Ingresar a la terminal"}
            </button>
          </form>
        )}

        {/* MODO 2: CREAR CUENTA */}
        {mode === "register" && (
          <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
            <div>
              <label
                htmlFor="reg-username"
                className="block text-xs font-medium text-slate-300 mb-1"
              >
                Nombre de usuario
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="reg-username"
                  type="text"
                  autoComplete="username"
                  value={regUsername}
                  onChange={(e) => setRegUsername(e.target.value)}
                  placeholder="ej. martin.juan"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                3 a 32 caracteres: minúsculas, números, punto o guion bajo.
              </p>
            </div>

            <div>
              <label
                htmlFor="reg-fullname"
                className="block text-xs font-medium text-slate-300 mb-1"
              >
                Nombre completo
              </label>
              <input
                id="reg-fullname"
                type="text"
                autoComplete="name"
                value={regFullName}
                onChange={(e) => setRegFullName(e.target.value)}
                placeholder="Nombre y apellido"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label
                htmlFor="reg-email"
                className="block text-xs font-medium text-slate-300 mb-1"
              >
                Correo electrónico (para recuperación de acceso)
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="tu.correo@dominio.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="reg-advisor"
                className="block text-xs font-medium text-slate-300 mb-1"
              >
                Ejecutivo a cargo (opcional)
              </label>
              <div className="relative">
                <UserCheck className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <select
                  id="reg-advisor"
                  value={regAdvisorId}
                  onChange={(e) => setRegAdvisorId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                >
                  <option value="">Sin ejecutivo (cuenta independiente)</option>
                  {advisors.map((adv) => (
                    <option key={adv.id} value={adv.id}>
                      {adv.full_name}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Si lo dejás en blanco, tu cartera será privada y solo visible para vos.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="reg-pass"
                  className="block text-xs font-medium text-slate-300 mb-1"
                >
                  Contraseña
                </label>
                <input
                  id="reg-pass"
                  type="password"
                  autoComplete="new-password"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="Mín. 8 caracteres"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>
              <div>
                <label
                  htmlFor="reg-pass-confirm"
                  className="block text-xs font-medium text-slate-300 mb-1"
                >
                  Confirmar clave
                </label>
                <input
                  id="reg-pass-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={regConfirmPassword}
                  onChange={(e) => setRegConfirmPassword(e.target.value)}
                  placeholder="Repetí la clave"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-colors cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              {submitting ? "Creando cuenta..." : "Registrarme e ingresar"}
            </button>
          </form>
        )}

        {/* MODO 3: RECUPERAR USUARIO Y CONTRASEÑA */}
        {mode === "recover" && (
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => switchMode("login")}
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Volver al inicio de sesión
            </button>

            <div>
              <h2 className="text-sm font-semibold text-slate-100">
                Recuperar usuario y contraseña
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Te enviaremos tu nombre de usuario registrado y un código válido
                por 15 minutos para definir una nueva clave.
              </p>
            </div>

            {recStep === "request" ? (
              <form onSubmit={handleRequestRecovery} className="space-y-3.5">
                <div>
                  <label
                    htmlFor="rec-email"
                    className="block text-xs font-medium text-slate-300 mb-1"
                  >
                    Correo electrónico registrado
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      id="rec-email"
                      type="email"
                      value={recEmail}
                      onChange={(e) => setRecEmail(e.target.value)}
                      placeholder="tu.correo@dominio.com"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-colors cursor-pointer"
                >
                  {submitting
                    ? "Enviando..."
                    : "Enviar código y recordar usuario"}
                </button>

                <button
                  type="button"
                  onClick={() => setRecStep("reset")}
                  className="w-full text-center text-[11px] text-slate-400 hover:text-emerald-400"
                >
                  Ya tengo un código de recuperación
                </button>
              </form>
            ) : (
              <form onSubmit={handleConfirmReset} className="space-y-3.5">
                <div>
                  <label
                    htmlFor="rec-token"
                    className="block text-xs font-medium text-slate-300 mb-1"
                  >
                    Código / Token de recuperación
                  </label>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      id="rec-token"
                      type="text"
                      value={recToken}
                      onChange={(e) => setRecToken(e.target.value)}
                      placeholder="Pegá el código recibido"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="rec-new-pass"
                    className="block text-xs font-medium text-slate-300 mb-1"
                  >
                    Nueva contraseña
                  </label>
                  <input
                    id="rec-new-pass"
                    type="password"
                    autoComplete="new-password"
                    value={recNewPassword}
                    onChange={(e) => setRecNewPassword(e.target.value)}
                    placeholder="Mínimo 8 caracteres"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-colors cursor-pointer"
                >
                  {submitting
                    ? "Actualizando..."
                    : "Guardar nueva clave e ingresar"}
                </button>

                <button
                  type="button"
                  onClick={() => setRecStep("request")}
                  className="w-full text-center text-[11px] text-slate-400 hover:text-emerald-400"
                >
                  Solicitar un nuevo código
                </button>
              </form>
            )}
          </div>
        )}

        {/* ACCESO SOCIAL OAUTH 2.0 (GOOGLE Y GITHUB) */}
        {mode !== "recover" && (
          <div className="mt-6">
            <div className="relative flex items-center justify-center mb-4">
              <div className="border-t border-slate-800 w-full" />
              <span className="bg-slate-900 px-3 whitespace-nowrap shrink-0 text-[11px] uppercase tracking-wider text-slate-500">
                o continuá con
              </span>
              <div className="border-t border-slate-800 w-full" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={Boolean(oauthLoading)}
                onClick={() => handleOAuthClick("google")}
                title={
                  providers.google
                    ? "Continuar con tu cuenta de Google"
                    : "Requiere configurar GOOGLE_CLIENT_ID en backend/.env"
                }
                className="flex items-center justify-center gap-2 bg-slate-950 hover:bg-slate-800/90 border border-slate-800 rounded-lg py-2.5 px-3 text-xs font-medium text-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <GoogleIcon />
                <span>
                  {oauthLoading === "google" ? "Conectando..." : "Google"}
                </span>
              </button>

              <button
                type="button"
                disabled={Boolean(oauthLoading)}
                onClick={() => handleOAuthClick("github")}
                title={
                  providers.github
                    ? "Continuar con tu cuenta de GitHub"
                    : "Requiere configurar GITHUB_CLIENT_ID en backend/.env"
                }
                className="flex items-center justify-center gap-2 bg-slate-950 hover:bg-slate-800/90 border border-slate-800 rounded-lg py-2.5 px-3 text-xs font-medium text-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <GitHubIcon />
                <span>
                  {oauthLoading === "github" ? "Conectando..." : "GitHub"}
                </span>
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-center gap-2 text-[11px] text-slate-500">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Sesión cifrada JWT · Roles RBAC · OAuth 2.0</span>
        </div>
      </div>
    </div>
  );
}