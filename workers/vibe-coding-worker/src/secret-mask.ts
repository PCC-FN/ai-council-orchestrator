const PATTERNS: Array<[RegExp, string]> = [
  [/api[_-]?key\s*[=:]\s*[^\s'"]+/gi, "api_key=********"],
  [/bearer\s+[a-zA-Z0-9._-]+/gi, "Bearer ********"],
  [/password\s*[=:]\s*[^\s'"]+/gi, "password=********"],
  [/sk-[a-zA-Z0-9]{8,}/g, "sk-********"],
];

export function maskSecrets(text: string): string {
  let out = text;
  for (const [pattern, repl] of PATTERNS) {
    out = out.replace(pattern, repl);
  }
  return out;
}
