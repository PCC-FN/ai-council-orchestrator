import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { discoverProjects, isPathWithinRoot, resolveProjectPath } from "../src/path-security.js";
import { maskSecrets } from "../src/secret-mask.js";

test("masks api keys", () => {
  assert.match(maskSecrets("OPENAI_API_KEY=sk-abcdefghijklmnop"), /\*\*\*\*\*\*\*\*/);
});

test("blocks path traversal", () => {
  assert.equal(isPathWithinRoot("C:\\Development\\..\\Windows", "C:\\Development"), false);
});

test("allows nested paths", () => {
  assert.equal(isPathWithinRoot("C:\\Development\\app\\src", "C:\\Development"), true);
});

test("resolve project path", () => {
  assert.ok(resolveProjectPath("C:\\Development\\demo", ["C:\\Development"]));
  assert.equal(resolveProjectPath("C:\\Other\\demo", ["C:\\Development"]), null);
});

test("discovers nested git repositories", () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "vibe-worker-"));
  try {
    const root = path.join(base, "root");
    const nested = path.join(root, "team", "app");
    fs.mkdirSync(nested, { recursive: true });
    fs.mkdirSync(path.join(root, "standalone", ".git"), { recursive: true });
    fs.mkdirSync(path.join(nested, ".git"), { recursive: true });
    fs.mkdirSync(path.join(root, "team", "node_modules", "pkg"), { recursive: true });
    fs.mkdirSync(path.join(root, "team", "node_modules", "pkg", ".git"), { recursive: true });

    const found = discoverProjects([root]);
    const paths = found.map((p) => p.local_path);
    assert.ok(paths.includes(path.join(root, "standalone")));
    assert.ok(paths.includes(nested));
    assert.equal(found.some((p) => p.local_path.includes("node_modules")), false);
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});

test("skips configured git root and discovers child repositories", () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "vibe-worker-root-git-"));
  try {
    const root = path.join(base, "drive");
    const childA = path.join(root, "ai-council-orchestrator");
    const childB = path.join(root, "infrastructure-explorer");
    fs.mkdirSync(childA, { recursive: true });
    fs.mkdirSync(childB, { recursive: true });
    fs.mkdirSync(path.join(root, ".git"), { recursive: true });
    fs.mkdirSync(path.join(childA, ".git"), { recursive: true });
    fs.mkdirSync(path.join(childB, ".git"), { recursive: true });

    const found = discoverProjects([root]);
    const paths = found.map((p) => p.local_path);
    assert.equal(paths.includes(root), false);
    assert.ok(paths.includes(childA));
    assert.ok(paths.includes(childB));
  } finally {
    fs.rmSync(base, { recursive: true, force: true });
  }
});
