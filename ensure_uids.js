#!/usr/bin/env node
/**
 * ensure_uids.js
 * - Adds `uid` to questions in bank_civil*.js files (only when missing).
 * - Ensures no duplicate uids across all matched bank files.
 *
 * Usage:
 *   node scripts/ensure_uids.js          # auto-detect bank_civil*.js in repo root
 *   node scripts/ensure_uids.js path/to/bank_civil.js path/to/bank_civil_2.js
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function pickFilesFromArgsOrCwd() {
  const args = process.argv.slice(2).filter(Boolean);
  if (args.length) return args;

  const cwd = process.cwd();
  return fs.readdirSync(cwd)
    .filter(f => /^bank_civil.*\.js$/i.test(f))
    .map(f => path.join(cwd, f))
    .sort();
}

function prefixForFile(filePath) {
  const base = path.basename(filePath).toLowerCase();
  if (base.includes("civil")) return "civ-";
  return "q-";
}

function extractUids(text) {
  const uids = [];
  const re = /\buid\s*:\s*["']([^"']+)["']/g;
  let m;
  while ((m = re.exec(text))) uids.push(m[1]);
  return uids;
}

function countQuestions(text) {
  // heuristic: count `question:` occurrences
  const re = /\bquestion\s*:\s*["'`]/g;
  return (text.match(re) || []).length;
}

function addMissingUids(text, uidPrefix) {
  // Insert uid right after the `id:` line, if the next line is not already uid.
  // Captures indentation used for `id:` so inserted uid aligns.
  const re = /(\{\s*\n)([ \t]*)id\s*:\s*(\d+)\s*,\s*\n(?!\2uid\s*:)/g;
  return text.replace(re, (_, objStart, indent, idNum) => {
    const uid = uidPrefix + crypto.randomUUID();
    return `${objStart}${indent}id: ${idNum},\n${indent}uid: "${uid}",\n`;
  });
}

function assertNoDuplicateUids(allUids) {
  const seen = new Set();
  for (const u of allUids) {
    if (seen.has(u)) {
      throw new Error(`Duplicate uid detected: ${u}`);
    }
    seen.add(u);
  }
}

function main() {
  const files = pickFilesFromArgsOrCwd();
  if (!files.length) {
    console.error("No bank_civil*.js files found.");
    process.exit(1);
  }

  // First pass: add missing uids + write back
  for (const fp of files) {
    const before = fs.readFileSync(fp, "utf-8");
    const after = addMissingUids(before, prefixForFile(fp));

    // Sanity: if some questions still have no uid, warn (usually means object has no `id:` line)
    const qCount = countQuestions(after);
    const uidCount = extractUids(after).length;
    if (uidCount < qCount) {
      console.warn(`[WARN] ${path.basename(fp)}: uidCount(${uidCount}) < questionCount(${qCount}). ` +
        `Some items may be missing "id:" line or have a nonstandard format.`);
    }

    if (after !== before) {
      fs.writeFileSync(fp, after, "utf-8");
      console.log(`[OK] Updated: ${fp}`);
    } else {
      console.log(`[OK] No change: ${fp}`);
    }
  }

  // Second pass: verify uniqueness across all files
  const allUids = [];
  for (const fp of files) {
    const text = fs.readFileSync(fp, "utf-8");
    allUids.push(...extractUids(text));
  }
  assertNoDuplicateUids(allUids);
  console.log(`[OK] UID uniqueness check passed. Total uids=${allUids.length}`);
}

main();
