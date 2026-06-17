import { NavLink } from "react-router-dom";
import { cn } from "../../utils/cn";
import { useSettings } from "../../hooks/useSettings";
import { Badge } from "../ui/Badge";

const NAV = [
  { to: "/", label: "Dashboard", end: true, icon: "▦" },
  { to: "/projects", label: "Projekte", icon: "▤" },
  { to: "/sessions/new", label: "Neues Feature", icon: "＋" },
  { to: "/vibe", label: "Vibe Coding", icon: "⌘" },
  { to: "/settings", label: "Einstellungen", icon: "⚙" },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const settings = useSettings();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-white px-3 py-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="px-2 pb-4">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            AO
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight text-slate-900 dark:text-slate-100">
              AI Orchestra
            </p>
            <p className="text-xs text-slate-500">Multi-Agent Betriebssystem</p>
          </div>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                isActive
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-200"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )
            }
          >
            <span className="w-4 text-center text-slate-400">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto px-2 pt-4">
        {settings?.mock_active && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
            <p className="font-semibold">Mock-Modus aktiv</p>
            <p className="mt-1">
              Keine API-Keys gesetzt — Agenten liefern realistische Beispielantworten.
            </p>
            <NavLink
              to="/settings"
              onClick={onNavigate}
              className="mt-2 inline-block font-medium text-amber-900 underline dark:text-amber-100"
            >
              API-Keys in Einstellungen hinterlegen →
            </NavLink>
          </div>
        )}
        {settings && (
          <div className="mt-3 flex items-center gap-1.5 px-1 text-xs text-slate-400">
            Compose2:
            <Badge tone={settings.compose2_mode === "manual" ? "warning" : "info"}>
              {settings.compose2_mode === "manual" ? "manuell" : "API"}
            </Badge>
          </div>
        )}
      </div>
    </aside>
  );
}
