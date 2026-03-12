"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Zap } from "lucide-react";
import { login } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(form.username, form.password);
      setUser({ username: data.username, role: data.role });
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Invalid username or password"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <Zap className="w-6 h-6 text-yellow-400" />
            <span className="text-2xl font-bold text-white">Ads Engine</span>
          </div>
          <p className="text-gray-400 text-sm">
            AI-powered ad management — sign in to continue
          </p>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Username
            </label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-yellow-400/40 focus:border-yellow-400 transition-colors"
              placeholder="vishnu"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-yellow-400/40 focus:border-yellow-400 transition-colors"
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-yellow-400 text-gray-950 font-semibold rounded-lg hover:bg-yellow-300 active:bg-yellow-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-6 bg-gray-900/50 border border-gray-800 rounded-lg p-4 space-y-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Demo accounts
          </p>
          {[
            { u: "vishnu", p: "admin123", r: "admin" },
            { u: "siva", p: "manager123", r: "manager" },
            { u: "vyas", p: "viewer123", r: "viewer" },
          ].map(({ u, p, r }) => (
            <button
              key={u}
              type="button"
              onClick={() => setForm({ username: u, password: p })}
              className="w-full text-left px-3 py-1.5 rounded text-xs text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
            >
              <span className="font-mono">{u}</span>
              <span className="text-gray-600"> / </span>
              <span className="font-mono">{p}</span>
              <span className="ml-2 text-gray-600 capitalize">({r})</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
