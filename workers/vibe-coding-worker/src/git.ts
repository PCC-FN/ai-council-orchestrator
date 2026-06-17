import { spawn } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(
  (cmd: string, args: string[], cwd: string, cb: (err: Error | null, stdout: string, stderr: string) => void) => {
    const child = spawn(cmd, args, { cwd, shell: false, windowsHide: true });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d.toString()));
    child.stderr.on("data", (d) => (stderr += d.toString()));
    child.on("close", (code) => {
      if (code !== 0) cb(new Error(stderr || stdout || `git exit ${code}`), stdout, stderr);
      else cb(null, stdout, stderr);
    });
    child.on("error", (err) => cb(err, stdout, stderr));
  },
);

export interface GitStatus {
  branch: string;
  clean: boolean;
  modified: string[];
  untracked: string[];
  staged: string[];
}

export async function runGit(cwd: string, args: string[]): Promise<string> {
  const [stdout] = await execFileAsync("git", args, cwd);
  return stdout.trim();
}

export async function getGitStatus(cwd: string): Promise<GitStatus> {
  const branch = await runGit(cwd, ["rev-parse", "--abbrev-ref", "HEAD"]).catch(() => "unknown");
  const porcelain = await runGit(cwd, ["status", "--porcelain"]).catch(() => "");
  const modified: string[] = [];
  const untracked: string[] = [];
  const staged: string[] = [];
  for (const line of porcelain.split("\n").filter(Boolean)) {
    const code = line.slice(0, 2);
    const file = line.slice(3).trim();
    if (code.startsWith("?")) untracked.push(file);
    else if (code[0] !== " ") staged.push(file);
    else modified.push(file);
  }
  return {
    branch,
    clean: porcelain.length === 0,
    modified,
    untracked,
    staged,
  };
}

export async function isGitRepo(cwd: string): Promise<boolean> {
  try {
    await runGit(cwd, ["rev-parse", "--git-dir"]);
    return true;
  } catch {
    return false;
  }
}

export async function createStash(cwd: string, message: string): Promise<string | null> {
  const status = await getGitStatus(cwd);
  if (status.clean) return null;
  await runGit(cwd, ["stash", "push", "-u", "-m", message]);
  return message;
}

export async function createBranch(cwd: string, branchName: string): Promise<void> {
  const exists = await runGit(cwd, ["branch", "--list", branchName]).catch(() => "");
  if (exists.includes(branchName)) {
    await runGit(cwd, ["checkout", branchName]);
  } else {
    await runGit(cwd, ["checkout", "-b", branchName]);
  }
}

export async function getDiff(cwd: string): Promise<string> {
  return runGit(cwd, ["diff", "HEAD"]).catch(() => runGit(cwd, ["diff"]));
}

export async function getChangedFiles(cwd: string): Promise<string[]> {
  const out = await runGit(cwd, ["diff", "--name-only", "HEAD"]).catch(() =>
    runGit(cwd, ["diff", "--name-only"]),
  );
  const untracked = await runGit(cwd, ["ls-files", "--others", "--exclude-standard"]).catch(() => "");
  const files = new Set([...out.split("\n").filter(Boolean), ...untracked.split("\n").filter(Boolean)]);
  return [...files];
}

export async function commitAll(cwd: string, message: string): Promise<string> {
  await runGit(cwd, ["add", "-A"]);
  await runGit(cwd, ["commit", "-m", message]);
  return runGit(cwd, ["rev-parse", "HEAD"]);
}

export async function pushBranch(
  cwd: string,
  branch: string,
  remote = "origin",
  force = false,
): Promise<void> {
  if (force) throw new Error("Force-Push ist standardmäßig verboten");
  await runGit(cwd, ["push", remote, branch]);
}

export async function restoreStash(cwd: string, stashRef = "stash@{0}"): Promise<void> {
  await runGit(cwd, ["stash", "apply", stashRef]).catch(() => {});
}

export interface GitPrepResult {
  ok: boolean;
  error?: string;
  stashMessage?: string;
  previousBranch?: string;
  status?: GitStatus;
}

export async function prepareGitWorkspace(
  cwd: string,
  branchName: string,
  jobId: string,
): Promise<GitPrepResult> {
  if (!(await isGitRepo(cwd))) {
    return { ok: true, status: { branch: "—", clean: true, modified: [], untracked: [], staged: [] } };
  }
  try {
    const status = await getGitStatus(cwd);
    const previousBranch = status.branch;
    let stashMessage: string | undefined;
    if (!status.clean) {
      stashMessage = `orchestra-backup-${jobId.slice(0, 8)}`;
      await createStash(cwd, stashMessage);
    }
    await createBranch(cwd, branchName);
    return { ok: true, stashMessage, previousBranch, status };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export async function captureGitResults(cwd: string): Promise<{
  diff: string;
  changedFiles: string[];
}> {
  if (!(await isGitRepo(cwd))) {
    return { diff: "", changedFiles: [] };
  }
  const [diff, changedFiles] = await Promise.all([getDiff(cwd), getChangedFiles(cwd)]);
  return { diff, changedFiles };
}
