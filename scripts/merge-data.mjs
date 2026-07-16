import { readdirSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, basename } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const QUESTIONS_DIR = join(ROOT, "data", "questions");
const ANSWERS_DIR = join(ROOT, "data", "answers");
const OUT_DIR = join(ROOT, "webapp", "data");

if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

function loadJson(path) {
  return JSON.parse(readFileSync(path, "utf-8"));
}

const SUBJECT_ALIASES = [
  [/^民事訴訟法.{0,2}和刑事訴訟法.{0,2}$/, "民事訴訟法大意與刑事訴訟法大意"],
  [/^民事訴訟法與刑事訴訟法大意$/, "民事訴訟法大意與刑事訴訟法大意"],
  [/^國文（?包括公文格式用語）?$/, "國文"],
  [/^國文\(包括公文格式用語\)$/, "國文"],
];

function normalizeSubject(subject) {
  for (const [pattern, canonical] of SUBJECT_ALIASES) {
    if (pattern.test(subject)) return canonical;
  }
  return subject;
}

const questionFiles = existsSync(QUESTIONS_DIR) ? readdirSync(QUESTIONS_DIR).filter((f) => f.endsWith(".json")) : [];
const index = [];
let totalQ = 0;
let missingAnswers = [];

for (const qf of questionFiles) {
  const q = loadJson(join(QUESTIONS_DIR, qf));
  const base = basename(qf, ".json");
  const answerPath = join(ANSWERS_DIR, `${base}.json`);
  let answerDoc = null;
  if (existsSync(answerPath)) {
    answerDoc = loadJson(answerPath);
  }
  const answers = answerDoc?.answers ?? [];
  const hasAnswers = answers.length === q.questions.length && answers.length > 0;
  if (!hasAnswers) missingAnswers.push(base);
  const subject = normalizeSubject(q.subject);

  const merged = {
    sourceFile: q.sourceFile ?? base,
    examYear: q.examYear,
    examName: q.examName,
    examCategory: q.examCategory,
    subject,
    answerSource: answerDoc?.source ?? null,
    answerConfidence: answerDoc?.confidence ?? "not-found",
    questions: q.questions.map((question, i) => ({
      index: question.index ?? i + 1,
      text: question.text,
      options: question.options,
      needsReview: !!question.needsReview,
      answer: hasAnswers ? answers[i] ?? null : null,
    })),
  };

  writeFileSync(join(OUT_DIR, `${base}.json`), JSON.stringify(merged));
  totalQ += merged.questions.length;

  if (merged.questions.length === 0) continue; // essay-only exam, nothing to quiz

  index.push({
    file: base,
    examYear: q.examYear,
    category: q.examCategory,
    subject,
    questionCount: merged.questions.length,
    hasAnswers,
  });
}

writeFileSync(join(OUT_DIR, "index.json"), JSON.stringify(index));

console.log(`Merged ${questionFiles.length} exams, ${totalQ} questions total.`);
console.log(`Exams missing full answer sets (${missingAnswers.length}):`);
for (const m of missingAnswers) console.log(" -", m);
