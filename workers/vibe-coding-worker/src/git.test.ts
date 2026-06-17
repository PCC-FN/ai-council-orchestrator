import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { prepareGitWorkspace, runGit } from "./git.js";

function git(repo: string, args: string[]): void {
  execFileSync("git", args, { cwd: repo, stdio: "ignore" });
}

test("runGit handles empty stdout", async () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "vibe-git-"));
  try {
    git(repo, ["init"]);
    git(repo, ["config", "user.email", "test@example.com"]);
    git(repo, ["config", "user.name", "Test"]);

    const listed = await runGit(repo, ["branch", "--list", "missing-branch"]);
    assert.equal(listed, "");

    const prep = await prepareGitWorkspace(repo, "orchestra/job-empty-test", "job-empty1");
    assert.equal(prep.ok, true);
  } finally {
    fs.rmSync(repo, { recursive: true, force: true });
  }
});
