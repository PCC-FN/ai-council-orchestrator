import test from "node:test";
import assert from "node:assert/strict";
import { isPathWithinRoot, resolveProjectPath } from "../src/path-security.js";
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
