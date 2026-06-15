import { useEffect, useState } from "react";
import { Api } from "../api/endpoints";
import type { RuntimeSettings } from "../types";

let cache: RuntimeSettings | null = null;

export function useSettings() {
  const [settings, setSettings] = useState<RuntimeSettings | null>(cache);

  useEffect(() => {
    if (cache) return;
    let alive = true;
    Api.getSettings()
      .then((s) => {
        cache = s;
        if (alive) setSettings(s);
      })
      .catch(() => {
        /* settings are optional; UI degrades gracefully */
      });
    return () => {
      alive = false;
    };
  }, []);

  return settings;
}
