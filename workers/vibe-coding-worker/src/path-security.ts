import fs from "node:fs";
import path from "node:path";

export function normalizePath(p: string): string {
  return path.resolve(path.normalize(p));
}

export function isPathWithinRoot(candidate: string, root: string): boolean {
  const cand = normalizePath(candidate);
  const rootPath = normalizePath(root);
  const rel = path.relative(rootPath, cand);
  return rel !== ".." && !rel.startsWith(`..${path.sep}`) && !path.isAbsolute(rel);
}

export function resolveProjectPath(projectPath: string, allowedRoots: string[]): string | null {
  const normalized = normalizePath(projectPath);
  for (const root of allowedRoots) {
    if (isPathWithinRoot(normalized, root)) return normalized;
  }
  return null;
}

export function discoverProjects(roots: string[]): Array<{ name: string; local_path: string; default_branch: string }> {
  const projects: Array<{ name: string; local_path: string; default_branch: string }> = [];
  const seen = new Set<string>();
  for (const root of roots) {
    const rootPath = normalizePath(root);
    if (!fs.existsSync(rootPath) || !fs.statSync(rootPath).isDirectory()) continue;
    const candidates = [rootPath];
    try {
      for (const entry of fs.readdirSync(rootPath, { withFileTypes: true })) {
        if (entry.isDirectory() && !entry.name.startsWith(".")) {
          candidates.push(path.join(rootPath, entry.name));
        }
      }
    } catch {
      continue;
    }
    for (const p of candidates) {
      if (seen.has(p)) continue;
      seen.add(p);
      projects.push({
        name: path.basename(p),
        local_path: p,
        default_branch: "main",
      });
    }
  }
  return projects;
}
