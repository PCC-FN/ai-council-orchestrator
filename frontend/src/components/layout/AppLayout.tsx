import { useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Button } from "../ui/Button";
import { useTheme } from "../../hooks/useTheme";
import { cn } from "../../utils/cn";

export function AppLayout({
  title,
  actions,
  children,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { theme, toggle } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-full">
      {/* Desktop sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute left-0 top-0 h-full">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Navigation öffnen"
          >
            ☰
          </Button>
          <h1 className="min-w-0 flex-1 truncate text-base font-semibold text-slate-900 dark:text-slate-100">
            {title}
          </h1>
          <div className="flex items-center gap-2">
            {actions}
            <Button
              variant="ghost"
              size="sm"
              onClick={toggle}
              aria-label="Theme wechseln"
              title={theme === "dark" ? "Helles Theme" : "Dunkles Theme"}
            >
              {theme === "dark" ? "☀" : "☾"}
            </Button>
          </div>
        </header>

        <main className={cn("flex-1 overflow-y-auto p-4 md:p-6")}>
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
