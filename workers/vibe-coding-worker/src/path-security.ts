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

const SKIP_DIR_NAMES = new Set([
  ".git",
  "node_modules",
  "vendor",
  "dist",
  "build",
  "target",
  "out",
  ".next",
  ".nuxt",
  ".venv",
  "venv",
  "__pycache__",
  ".cache",
  ".turbo",
  "coverage",
  "$recycle.bin",
  "system volume information",
]);

export function isGitRepository(dirPath: string): boolean {
  return isGitWorkTree(dirPath);
}

function readConfiguredWorkTree(gitDir: string): string | null {
  try {
    const configPath = path.join(gitDir, "config");
    if (!fs.existsSync(configPath)) return null;
    const config = fs.readFileSync(configPath, "utf8");
    const match = config.match(/^\s*worktree\s*=\s*(.+)$/m);
    return match ? normalizePath(match[1].trim()) : null;
  } catch {
    return null;
  }
}

/** True only when dirPath is the checkout root, not a bare repo or external worktree metadata. */
export function isGitWorkTree(dirPath: string): boolean {
  try {
    const normalizedDir = normalizePath(dirPath);
    const gitPath = path.join(dirPath, ".git");
    if (!fs.existsSync(gitPath)) return false;

    const stat = fs.statSync(gitPath);
    if (stat.isDirectory()) {
      if (!fs.existsSync(path.join(gitPath, "HEAD"))) return false;
      const worktree = readConfiguredWorkTree(gitPath);
      if (worktree && worktree !== normalizedDir) return false;
      return true;
    }

    const gitFile = fs.readFileSync(gitPath, "utf8").trim();
    if (!gitFile.startsWith("gitdir:")) return false;
    const gitdir = normalizePath(path.resolve(dirPath, gitFile.slice("gitdir: ".length).trim()));
    if (!fs.existsSync(path.join(gitdir, "HEAD"))) return false;
    const worktree = readConfiguredWorkTree(gitdir);
    if (worktree && worktree !== normalizedDir) return false;
    return true;
  } catch {
    return false;
  }
}

function shouldSkipDir(name: string): boolean {
  if (!name) return true;
  if (name.startsWith(".") && name !== ".") return true;
  return SKIP_DIR_NAMES.has(name.toLowerCase());
}

function projectDisplayName(repoPath: string, rootPath: string): string {
  const rel = path.relative(rootPath, repoPath);
  if (!rel || rel === ".") return path.basename(repoPath) || repoPath;
  const base = path.basename(repoPath);
  const parent = path.dirname(rel);
  if (!parent || parent === ".") return base;
  return `${parent.replaceAll(path.sep, "/")}/${base}`;
}

function walkForGitRepos(
  dirPath: string,
  rootPath: string,
  configuredRoots: Set<string>,
  projects: Map<string, { name: string; local_path: string; default_branch: string }>,
  depth: number,
  maxDepth: number,
): void {
  if (depth > maxDepth) return;

  const normalized = normalizePath(dirPath);
  const isConfiguredRoot = configuredRoots.has(normalized);

  if (isGitRepository(dirPath) && !isConfiguredRoot) {
    if (!projects.has(normalized)) {
      projects.set(normalized, {
        name: projectDisplayName(normalized, rootPath),
        local_path: normalized,
        default_branch: "main",
      });
    }
    return;
  }

  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dirPath, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (shouldSkipDir(entry.name)) continue;
    walkForGitRepos(
      path.join(dirPath, entry.name),
      rootPath,
      configuredRoots,
      projects,
      depth + 1,
      maxDepth,
    );
  }
}

export function discoverProjects(
  roots: string[],
  maxDepth = 16,
): Array<{ name: string; local_path: string; default_branch: string }> {
  const projects = new Map<string, { name: string; local_path: string; default_branch: string }>();
  const configuredRoots = new Set(roots.map((root) => normalizePath(root)));

  for (const root of roots) {
    const rootPath = normalizePath(root);
    if (!fs.existsSync(rootPath) || !fs.statSync(rootPath).isDirectory()) continue;
    walkForGitRepos(rootPath, rootPath, configuredRoots, projects, 0, maxDepth);
  }

  return [...projects.values()].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
}
