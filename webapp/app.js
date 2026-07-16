const app = document.getElementById("app");
let INDEX = [];
let examCache = {};

function goHome() {
  location.hash = "#/";
}

async function loadIndex() {
  if (INDEX.length) return INDEX;
  const res = await fetch("data/index.json");
  INDEX = await res.json();
  return INDEX;
}

async function loadExam(file) {
  if (examCache[file]) return examCache[file];
  const res = await fetch(`data/${encodeURIComponent(file)}.json`);
  const data = await res.json();
  examCache[file] = data;
  return data;
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function optionTag(i) {
  return ["Ａ", "Ｂ", "Ｃ", "Ｄ"][i] || String(i + 1);
}

async function renderHome() {
  const idx = await loadIndex();
  const bySubject = {};
  for (const e of idx) {
    (bySubject[e.subject] ??= []).push(e);
  }
  app.innerHTML = "";
  app.appendChild(el(`<div class="card"><h2>選擇科目開始練習</h2><p style="color:var(--muted);font-size:0.85rem;margin:0">共 ${idx.length} 份試題，${idx.reduce((s, e) => s + e.questionCount, 0)} 題</p></div>`));
  const grid = el(`<div class="grid"></div>`);
  for (const subject of Object.keys(bySubject).sort()) {
    const exams = bySubject[subject];
    const qCount = exams.reduce((s, e) => s + e.questionCount, 0);
    const withAns = exams.filter((e) => e.hasAnswers).length;
    const btn = el(`<button class="pick-btn"><strong>${subject}</strong><span class="sub">${exams.length} 份試題・${qCount} 題・${withAns}/${exams.length} 份有解答</span></button>`);
    btn.onclick = () => {
      location.hash = `#/subject/${encodeURIComponent(subject)}`;
    };
    grid.appendChild(btn);
  }
  app.appendChild(grid);
}

async function renderSubject(subject) {
  const idx = await loadIndex();
  const exams = idx.filter((e) => e.subject === subject).sort((a, b) => b.examYear - a.examYear || a.category.localeCompare(b.category));
  app.innerHTML = "";
  app.appendChild(el(`<div class="breadcrumb"><a onclick="goHome()">← 所有科目</a></div>`));
  app.appendChild(el(`<div class="card"><h2>${subject}</h2></div>`));
  const grid = el(`<div class="grid"></div>`);
  for (const e of exams) {
    const disabled = !e.hasAnswers;
    const btn = el(
      `<button class="pick-btn ${disabled ? "warn" : ""}"><strong>${e.examYear} 年・${e.category}</strong><span class="sub">${e.questionCount} 題${disabled ? "（尚無解答，暫僅供瀏覽）" : ""}</span></button>`
    );
    btn.onclick = () => {
      location.hash = `#/quiz/${encodeURIComponent(e.file)}`;
    };
    grid.appendChild(btn);
  }
  app.appendChild(grid);
}

function quizState(file, data) {
  return {
    file,
    data,
    i: 0,
    answers: new Array(data.questions.length).fill(null),
    revealed: new Array(data.questions.length).fill(false),
  };
}

async function renderQuiz(file) {
  const data = await loadExam(file);
  const state = quizState(file, data);
  drawQuestion(state);
}

function drawQuestion(state) {
  const { data, i } = state;
  const q = data.questions[i];
  app.innerHTML = "";
  app.appendChild(
    el(`<div class="breadcrumb"><a onclick="goHome()">← 所有科目</a> / <a onclick="location.hash='#/subject/${encodeURIComponent(data.subject)}'">${data.subject}</a> / ${data.examYear} 年 ${data.examCategory}</div>`)
  );
  const card = el(`<div class="card"></div>`);
  card.appendChild(el(`<div class="q-progress">第 ${i + 1} / ${data.questions.length} 題${q.needsReview ? '<span class="badge">題目擷取待人工核對</span>' : ""}</div>`));
  card.appendChild(el(`<div class="q-text">${escapeHtml(q.text)}</div>`));

  const hasAnswer = typeof q.answer === "number" && q.answer >= 1;
  const revealed = state.revealed[i];

  q.options.forEach((optText, oi) => {
    const optNum = oi + 1;
    const b = el(`<button class="opt"><span class="tag">${optionTag(oi)}</span><span>${escapeHtml(optText)}</span></button>`);
    if (revealed) {
      b.disabled = true;
      if (hasAnswer && optNum === q.answer) b.classList.add("correct");
      if (state.answers[i] === optNum && optNum !== q.answer) b.classList.add("wrong");
      if (state.answers[i] === optNum) b.classList.add("selected");
    }
    b.onclick = () => {
      if (state.revealed[i]) return;
      state.answers[i] = optNum;
      state.revealed[i] = true;
      drawQuestion(state);
    };
    card.appendChild(b);
  });

  if (revealed && !hasAnswer) {
    card.appendChild(el(`<p style="color:var(--muted);font-size:0.85rem">此題目前查無官方解答，不列入計分。</p>`));
  }

  app.appendChild(card);

  const nav = el(`<div class="nav-row"></div>`);
  const prev = el(`<button class="secondary">上一題</button>`);
  prev.disabled = i === 0;
  prev.onclick = () => {
    state.i--;
    drawQuestion(state);
  };
  nav.appendChild(prev);

  if (i < data.questions.length - 1) {
    const next = el(`<button class="primary">${revealed ? "下一題" : "跳過"}</button>`);
    next.onclick = () => {
      state.i++;
      drawQuestion(state);
    };
    nav.appendChild(next);
  } else {
    const finish = el(`<button class="primary">完成測驗，查看成績</button>`);
    finish.onclick = () => renderResult(state);
    nav.appendChild(finish);
  }
  app.appendChild(nav);
}

function renderResult(state) {
  const { data } = state;
  const scored = data.questions
    .map((q, idx) => ({ q, idx }))
    .filter(({ q }) => typeof q.answer === "number" && q.answer >= 1);
  const correct = scored.filter(({ q, idx }) => state.answers[idx] === q.answer).length;
  const answered = scored.filter(({ idx }) => state.answers[idx] !== null).length;

  app.innerHTML = "";
  app.appendChild(el(`<div class="breadcrumb"><a onclick="goHome()">← 所有科目</a></div>`));
  const hero = el(`<div class="card score-hero"></div>`);
  hero.appendChild(el(`<div>${data.examYear} 年 ${data.examCategory}・${data.subject}</div>`));
  hero.appendChild(el(`<div class="big">${correct} / ${scored.length}</div>`));
  hero.appendChild(el(`<div style="color:var(--muted)">已作答 ${answered} 題（可計分題數 ${scored.length}／全部 ${data.questions.length} 題）</div>`));
  const retry = el(`<button class="primary" style="margin-top:0.75rem">重新測驗本份試題</button>`);
  retry.onclick = () => renderQuiz(state.file);
  hero.appendChild(retry);
  app.appendChild(hero);

  data.questions.forEach((q, idx) => {
    const hasAnswer = typeof q.answer === "number" && q.answer >= 1;
    const isCorrect = hasAnswer && state.answers[idx] === q.answer;
    const item = el(`<div class="card review-item ${hasAnswer ? (isCorrect ? "correct" : "wrong") : ""}"></div>`);
    item.appendChild(el(`<div class="q-progress">第 ${idx + 1} 題</div>`));
    item.appendChild(el(`<div class="q-text">${escapeHtml(q.text)}</div>`));
    q.options.forEach((optText, oi) => {
      const optNum = oi + 1;
      const b = el(`<div class="opt"><span class="tag">${optionTag(oi)}</span><span>${escapeHtml(optText)}</span></div>`);
      if (hasAnswer && optNum === q.answer) b.classList.add("correct");
      if (state.answers[idx] === optNum && optNum !== q.answer) b.classList.add("wrong");
      item.appendChild(b);
    });
    app.appendChild(item);
  });
}

function escapeHtml(s) {
  return (s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function router() {
  const hash = location.hash || "#/";
  const [, route, arg] = hash.match(/^#\/([^/]*)\/?(.*)$/) || [];
  try {
    if (!route) return renderHome();
    if (route === "subject") return renderSubject(decodeURIComponent(arg));
    if (route === "quiz") return renderQuiz(decodeURIComponent(arg));
    return renderHome();
  } catch (err) {
    app.innerHTML = `<div class="card">載入失敗：${escapeHtml(err.message)}</div>`;
  }
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);
