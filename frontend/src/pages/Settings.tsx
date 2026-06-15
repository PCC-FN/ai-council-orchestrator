import { useCallback, useEffect, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { Field, Input } from "../components/ui/Field";
import { Badge } from "../components/ui/Badge";
import { LoadingState, ErrorState, InlineError } from "../components/common/States";
import { Api } from "../api/endpoints";
import { invalidateSettingsCache } from "../hooks/useSettings";
import type { ProviderKeyInfo, RuntimeSettings, SettingsUpdate } from "../types";

type SecretDraft = {
  value: string;
  touched: boolean;
  clear: boolean;
};

function sourceLabel(source: ProviderKeyInfo["source"]) {
  if (source === "database") return "WebUI";
  if (source === "env") return ".env";
  return "nicht gesetzt";
}

function sourceTone(source: ProviderKeyInfo["source"]): "success" | "info" | "neutral" {
  if (source === "database") return "success";
  if (source === "env") return "info";
  return "neutral";
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [compose2Mode, setCompose2Mode] = useState<"manual" | "api">("manual");
  const [useMock, setUseMock] = useState(false);
  const [openaiModel, setOpenaiModel] = useState("");
  const [anthropicModel, setAnthropicModel] = useState("");
  const [compose2Url, setCompose2Url] = useState("");
  const [secrets, setSecrets] = useState<Record<string, SecretDraft>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await Api.getSettings();
      setSettings(s);
      setCompose2Mode(s.compose2_mode);
      setUseMock(s.use_mock_providers);
      setOpenaiModel(s.default_openai_model);
      setAnthropicModel(s.default_anthropic_model);
      setCompose2Url(s.compose2_base_url);
      setSecrets(
        Object.fromEntries(
          s.provider_keys.map((pk) => [
            pk.key,
            { value: "", touched: false, clear: false } satisfies SecretDraft,
          ]),
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setSecret = (key: string, patch: Partial<SecretDraft>) => {
    setSecrets((prev) => ({
      ...prev,
      [key]: { ...prev[key], ...patch },
    }));
    setSaved(false);
  };

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const body: SettingsUpdate = {
        compose2_mode: compose2Mode,
        use_mock_providers: useMock,
        default_openai_model: openaiModel,
        default_anthropic_model: anthropicModel,
        compose2_base_url: compose2Url,
      };

      for (const pk of settings.provider_keys) {
        const draft = secrets[pk.key];
        if (!draft) continue;
        if (draft.clear) {
          (body as Record<string, string | null>)[pk.key] = "";
        } else if (draft.touched && draft.value.trim()) {
          (body as Record<string, string | null>)[pk.key] = draft.value.trim();
        }
      }

      const updated = await Api.updateSettings(body);
      invalidateSettingsCache();
      setSettings(updated);
      setSecrets(
        Object.fromEntries(
          updated.provider_keys.map((pk) => [
            pk.key,
            { value: "", touched: false, clear: false } satisfies SecretDraft,
          ]),
        ),
      );
      setSaved(true);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout
      title="Einstellungen"
      actions={
        <Button size="sm" onClick={save} loading={saving} disabled={!settings}>
          Speichern
        </Button>
      }
    >
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !settings ? null : (
        <div className="space-y-8">
          {saveError && <InlineError message={saveError} />}
          {saved && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
              Einstellungen gespeichert. Provider nutzen die neuen Werte ab der nächsten
              Agenten-Runde.
            </div>
          )}

          {settings.mock_active && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
              <p className="font-semibold">Mock-Modus aktiv</p>
              <p className="mt-1 text-amber-800 dark:text-amber-200">
                OpenAI- und Anthropic-Schlüssel fehlen oder Mock ist erzwungen — Agenten liefern
                Beispielantworten ohne echte API-Aufrufe.
              </p>
            </div>
          )}

          <section className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Provider API-Schlüssel
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Schlüssel werden nur serverseitig gespeichert. Leer lassen = unverändert. Mit
              „Entfernen“ wird der in der WebUI gespeicherte Wert gelöscht (Fallback auf .env).
            </p>

            <div className="mt-5 space-y-5">
              {settings.provider_keys.map((pk) => {
                const draft = secrets[pk.key] ?? { value: "", touched: false, clear: false };
                return (
                  <div
                    key={pk.key}
                    className="rounded-lg border border-slate-100 p-4 dark:border-slate-800"
                  >
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                        {pk.label}
                      </span>
                      {!pk.available && (
                        <Badge tone="neutral">Demnächst</Badge>
                      )}
                      {pk.configured && (
                        <Badge tone="success">
                          {pk.masked_hint ?? "gesetzt"}
                        </Badge>
                      )}
                      <Badge tone={sourceTone(pk.source)}>{sourceLabel(pk.source)}</Badge>
                    </div>
                    <p className="mb-3 text-xs text-slate-500">{pk.description}</p>
                    <Field label={`${pk.label} API Key`} hint={pk.env_var}>
                      <Input
                        type="password"
                        autoComplete="off"
                        placeholder={
                          pk.configured
                            ? "Neuen Schlüssel eingeben (leer = unverändert)"
                            : pk.placeholder || "API-Schlüssel eingeben"
                        }
                        value={draft.clear ? "" : draft.value}
                        disabled={draft.clear || !pk.available}
                        onChange={(e) =>
                          setSecret(pk.key, {
                            value: e.target.value,
                            touched: true,
                            clear: false,
                          })
                        }
                      />
                    </Field>
                    {pk.configured && pk.source === "database" && (
                      <label className="mt-2 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                        <input
                          type="checkbox"
                          checked={draft.clear}
                          onChange={(e) =>
                            setSecret(pk.key, {
                              clear: e.target.checked,
                              value: "",
                              touched: true,
                            })
                          }
                        />
                        Gespeicherten Schlüssel entfernen
                      </label>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Modelle & Compose2
            </h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="OpenAI Modell">
                <Input
                  value={openaiModel}
                  onChange={(e) => {
                    setOpenaiModel(e.target.value);
                    setSaved(false);
                  }}
                  placeholder="gpt-4o-mini"
                />
              </Field>
              <Field label="Anthropic Modell">
                <Input
                  value={anthropicModel}
                  onChange={(e) => {
                    setAnthropicModel(e.target.value);
                    setSaved(false);
                  }}
                  placeholder="claude-3-5-sonnet-20241022"
                />
              </Field>
              <Field label="Compose2 Modus">
                <select
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
                  value={compose2Mode}
                  onChange={(e) => {
                    setCompose2Mode(e.target.value as "manual" | "api");
                    setSaved(false);
                  }}
                >
                  <option value="manual">Manuell (Copy & Paste)</option>
                  <option value="api">API (HTTP-Endpunkt)</option>
                </select>
              </Field>
              <Field label="Compose2 Base URL" hint="nur API-Modus">
                <Input
                  value={compose2Url}
                  onChange={(e) => {
                    setCompose2Url(e.target.value);
                    setSaved(false);
                  }}
                  placeholder="https://compose2.example/api"
                  disabled={compose2Mode !== "api"}
                />
              </Field>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Entwicklung
            </h2>
            <label className="mt-4 flex items-start gap-3 text-sm text-slate-700 dark:text-slate-200">
              <input
                type="checkbox"
                className="mt-1"
                checked={useMock}
                onChange={(e) => {
                  setUseMock(e.target.checked);
                  setSaved(false);
                }}
              />
              <span>
                <span className="font-medium">Mock-Provider erzwingen</span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  Ignoriert echte API-Schlüssel und liefert offline Demo-Antworten — nützlich für
                  Tests ohne Kosten.
                </span>
              </span>
            </label>
          </section>
        </div>
      )}
    </AppLayout>
  );
}
