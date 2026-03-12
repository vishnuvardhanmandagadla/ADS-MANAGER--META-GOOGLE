import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  CheckSquare,
  Megaphone,
  MessageSquare,
  Settings,
  LogOut,
  Zap,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/approvals", label: "Approvals", icon: CheckSquare, badge: true },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  { href: "/ai-chat", label: "AI Chat", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  pendingCount?: number;
  user?: { username: string; role: string } | null;
  onLogout?: () => void;
}

export default function Sidebar({ pendingCount = 0, user, onLogout }: SidebarProps) {
  const location = useLocation();

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-gray-950 text-white border-r border-gray-800 flex-shrink-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-400" />
          <span className="font-bold text-lg tracking-tight">Ads Engine</span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">AI-powered ad management</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon, badge }) => {
          const active = location.pathname === href || location.pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              to={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-800/60 hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{label}</span>
              {badge && pendingCount > 0 && (
                <span className="bg-yellow-400 text-gray-950 text-xs font-bold px-1.5 py-0.5 rounded-full leading-none">
                  {pendingCount > 99 ? "99+" : pendingCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      {user && (
        <div className="px-4 py-4 border-t border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-yellow-400/20 text-yellow-400 flex items-center justify-center text-sm font-bold flex-shrink-0">
              {user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user.username}</p>
              <p className="text-xs text-gray-500 capitalize">{user.role}</p>
            </div>
            <button
              onClick={onLogout}
              className="p-1.5 text-gray-500 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
