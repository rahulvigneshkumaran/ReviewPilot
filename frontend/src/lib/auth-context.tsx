"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { api, UserProfile } from "./api";

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkAuth() {
      try {
        const profile = await api.getCurrentUser();
        setUser(profile);
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    checkAuth();
  }, []);

  const login = () => {
    // Directs the user to the FastAPI backend GitHub OAuth route — uses env var in production
    if (typeof window !== "undefined") {
      const backendBase =
        process.env.NEXT_PUBLIC_API_URL ??
        "https://reviewpilot-hvrp.onrender.com/api/v1";
      window.location.href = `${backendBase}/auth/login`;
    }
  };

  const logout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      setUser(null);
      window.location.href = "/login";
    }
  };

  const isAuthenticated = !!user;

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
