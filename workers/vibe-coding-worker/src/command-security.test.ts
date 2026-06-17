import test from "node:test";
import assert from "node:assert/strict";
import { classifyCommand, assertCommandAllowed } from "../src/command-security.js";

test("git status is safe", () => {
  assert.equal(classifyCommand("git status"), "safe");
});

test("git push requires confirmation", () => {
  assert.equal(classifyCommand("git push origin main"), "confirmation");
});

test("forbidden commands blocked", () => {
  assert.equal(classifyCommand("format C: /y"), "forbidden");
});

test("assertCommandAllowed blocks push without flag", () => {
  assert.throws(() => assertCommandAllowed("git push origin main", false));
});

test("assertCommandAllowed allows push with flag", () => {
  assert.doesNotThrow(() => assertCommandAllowed("git push origin main", true));
});
