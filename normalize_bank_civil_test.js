// normalize_bank_civil_test.js
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "bank_civil_test.js");
const OUT = path.join(__dirname, "bank_civil_test.normalized.js");

global.window = {};
require(SRC);

const data = window.BANK_CIVIL_TEST;

if (!Array.isArray(data)) {
  throw new Error("BANK_CIVIL_TEST is not an array");
}

const errors = [];

data.forEach((q, idx) => {
  // --- A. key normalize
  if (q.answerIndex === undefined && q.answerindex !== undefined) {
    q.answerIndex = q.answerindex;
    delete q.answerindex;
  }

  const nChoices = Array.isArray(q.choices) ? q.choices.length : 0;

  let ai = Number(q.answerIndex);

  if (!Number.isFinite(ai)) {
    errors.push({ idx, id: q.id, uid: q.uid, reason: "answerIndex not number" });
    return;
  }

  // --- C. 1-based detection
  if (ai === nChoices) {
    ai = ai - 1;
  }

  // --- range check
  if (ai < 0 || ai >= nChoices) {
    errors.push({
      idx,
      id: q.id,
      uid: q.uid,
      reason: `answerIndex out of range (${ai} / ${nChoices})`
    });
    return;
  }

  q.answerIndex = ai;
});

// --- write output
const output =
  "window.BANK_CIVIL_TEST = " +
  JSON.stringify(data, null, 2) +
  ";\n";

fs.writeFileSync(OUT, output, "utf-8");

// --- report
console.log("✅ normalization done");
console.log(`총 문제 수: ${data.length}`);
console.log(`오류 문제 수: ${errors.length}`);

if (errors.length) {
  console.log("❌ 오류 목록:");
  errors.forEach(e => console.log(e));
}
