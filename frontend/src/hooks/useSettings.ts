import { useCallback, useEffect, useState } from "react";
import { Api } from "../api/endpoints";
import type { RuntimeSettings } from "../types";

let cache: RuntimeSettings | null = null;

export function invalidateSettingsCache() {
  cache = null;
}

export function useSettings() {
  const [settings, setSettings] = useState<RuntimeSettings | null>(cache);

  const refresh = useCallback(async () => {
    try {
      const s = await Api.getSettings();
      cache = s;
      setSettings(s);
    } catch {
      /* settings are optional; UI degrades gracefully */
    }
  }, []);

  useEffect(() => {
    if (cache) return;
    void refresh();
  }, [refresh]);

  return settings;
}

export function useSettingsRefresh() {
  return invalidateSettingsCache;
}
