import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import apiClient, { setStoredToken } from "../api/client";
import { AuthProvider } from "../context/AuthContext";
import LoginScreen from "../components/auth/LoginScreen";
import UserManagementModal from "../components/auth/UserManagementModal";
import { AuthContext } from "../context/authStore";

vi.mock("../api/client", () => {
  const mockClient = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return {
    default: mockClient,
    API_BASE_URL: "/api/v1",
    getStoredToken: vi.fn(() => null),
    setStoredToken: vi.fn(),
  };
});

describe("Etapa 11B — Autenticación y RBAC en Frontend", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra error de validación si se envía LoginScreen vacío", async () => {
    render(
      <AuthProvider>
        <LoginScreen />
      </AuthProvider>
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Ingresar a la Terminal/i })
    );

    expect(
      await screen.findByText(/Completá tu correo electrónico y contraseña/i)
    ).toBeInTheDocument();
  });

  it("ejecuta login exitoso y guarda el access_token", async () => {
    apiClient.post.mockResolvedValueOnce({
      data: {
        access_token: "jwt-token-demo",
        user: {
          id: 1,
          email: "admin@vektorterminal.local",
          full_name: "Administrador Vektor",
          role: "superadmin",
          is_active: true,
          must_change_password: false,
        },
      },
    });

    render(
      <AuthProvider>
        <LoginScreen />
      </AuthProvider>
    );

    fireEvent.change(screen.getByLabelText(/Correo electrónico/i), {
      target: { value: "admin@vektorterminal.local" },
    });
    fireEvent.change(screen.getByLabelText(/Contraseña/i), {
      target: { value: "Admin1234!" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Ingresar a la Terminal/i })
    );

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/auth/login", {
        email: "admin@vektorterminal.local",
        password: "Admin1234!",
      });
      expect(setStoredToken).toHaveBeenCalledWith("jwt-token-demo");
    });
  });

  it("muestra formulario de alta en UserManagementModal solo para superadmin", async () => {
    apiClient.get.mockResolvedValueOnce({
      data: {
        users: [
          {
            id: 1,
            email: "admin@vektorterminal.local",
            full_name: "Administrador Vektor",
            role: "superadmin",
            is_active: true,
            advisor_name: null,
          },
        ],
      },
    });

    render(
      <AuthContext.Provider
        value={{
          user: { id: 1, role: "superadmin" },
          isSuperAdmin: true,
          isAdvisorOrAdmin: true,
          isClient: false,
        }}
      >
        <UserManagementModal isOpen={true} onClose={() => {}} />
      </AuthContext.Provider>
    );

    expect(
      await screen.findByText(/Administración de Usuarios y Roles/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Alta de nuevo usuario/i)).toBeInTheDocument();
  });

  it("oculta formulario de alta en UserManagementModal cuando el rol es advisor", async () => {
    apiClient.get.mockResolvedValueOnce({
      data: {
        users: [
          {
            id: 3,
            email: "cliente@vektor.local",
            full_name: "Cliente Demo",
            role: "client",
            is_active: true,
            advisor_name: "Asesor Demo",
          },
        ],
      },
    });

    render(
      <AuthContext.Provider
        value={{
          user: { id: 2, role: "advisor" },
          isSuperAdmin: false,
          isAdvisorOrAdmin: true,
          isClient: false,
        }}
      >
        <UserManagementModal isOpen={true} onClose={() => {}} />
      </AuthContext.Provider>
    );

    expect(
      await screen.findByText(/Mis Clientes Asignados/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Alta de nuevo usuario/i)
    ).not.toBeInTheDocument();
  });
});