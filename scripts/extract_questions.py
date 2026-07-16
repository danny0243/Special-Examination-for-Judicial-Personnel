# -*- coding: utf-8 -*-
import os
import re
import json
import pdfplumber

BASE = r"D:\OneDrive - ncut.edu.tw\國立勤益科技大學\系統開發\司法五等-20260716T010343Z-1-001\司法五等"
OUT_DIR = r"D:\OneDrive - ncut.edu.tw\國立勤益科技大學\系統開發\司法五等-20260716T010343Z-1-001\data\questions"

os.makedirs(OUT_DIR, exist_ok=True)

FOOTER_PATTERNS = [
    re.compile(r"全國最大公教職網站"),
    re.compile(r"public\.com\.tw"),
    re.compile(r"共\s*\d+\s*頁"),
    re.compile(r"第\s*\d+\s*頁"),
]
HEADER_PATTERNS = [
    re.compile(r"歷屆[試詴]題"),
    re.compile(r"公職王"),
    re.compile(r"考試別[：:]"),
    re.compile(r"等\s*別[：:]"),
    re.compile(r"類科組別?[：:]"),
    re.compile(r"類\s*科[：:]"),
    re.compile(r"類科別[：:]"),
    re.compile(r"類\s*別[：:]"),
    re.compile(r"考試類別[：:]"),
    re.compile(r"甄試類科"),
    re.compile(r"^專業科目"),
    re.compile(r"^共同科目"),
    re.compile(r"科\s*目[：:]"),
    re.compile(r"考試時間[：:]"),
    re.compile(r"考試名稱[：:]"),
    re.compile(r"^說明[：:].{0,30}選項"),
    re.compile(r"^[一二三四五六七八九十]、單選題"),
    re.compile(r"^[壹貳參]、.{0,20}選擇題"),
    re.compile(r"^.{2,4}老師$"),
    re.compile(r"^\d+\s*年.*[考詴][試詴]{0,1}試?題$"),
    re.compile(r"^\d+\s*年.*考[試詴].*[試詴]題"),
    re.compile(r"^\d+\s*年.*考[試詴].{0,20}類別[：:].*$"),
    re.compile(r"特種考[試詴].{0,15}(考[試詴]|人員)$"),
    re.compile(r"特種考[試詴]"),
    re.compile(r"考[試詴][試詴]題$"),
    re.compile(r"聯合統一考試"),
    re.compile(r"^[甲乙丙丁戊]、.{0,10}部分([：:（(]|$)"),
]

STEM_END_RE = re.compile(r"[？?]\s*$")

# PUA glyph markers used by some source PDFs to mark option ①②③④
OPT_CHARS = ""
OPT_CHAR_SET = set(OPT_CHARS)
QSTART_CLASS = "--"
BOUNDARY_RE = re.compile(f"[{OPT_CHARS}]\\s*[{QSTART_CLASS}]")
ANY_PUA_RE = re.compile("[-]")


WATERMARK_STRAY_RE = re.compile(r"^[公職王]{1,2}$")


def is_noise(line_text):
    if WATERMARK_STRAY_RE.match(line_text.strip()):
        return True
    for p in FOOTER_PATTERNS + HEADER_PATTERNS:
        if p.search(line_text):
            return True
    return False


def cluster_lines(words, y_tol=3):
    lines = []
    cur = []
    cur_top = None
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if cur_top is None or abs(w["top"] - cur_top) <= y_tol:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append(cur)
            cur = [w]
            cur_top = w["top"]
    if cur:
        lines.append(cur)
    return lines


def segment_line(line_words, x_gap=14):
    line_words = sorted(line_words, key=lambda w: w["x0"])
    segments = []
    cur_words = [line_words[0]]
    for prev, w in zip(line_words, line_words[1:]):
        if w["x0"] - prev["x1"] > x_gap:
            segments.append(cur_words)
            cur_words = [w]
        else:
            cur_words.append(w)
    segments.append(cur_words)
    texts = []
    for seg in segments:
        texts.append("".join(w["text"] for w in seg))
    return texts


def clean_lines_for_pdf(path):
    """Return (plain_text_lines, has_pua) using extract_text, noise-stripped."""
    all_lines = []
    has_pua = False
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if ANY_PUA_RE.search(text):
                has_pua = True
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if is_noise(line):
                    continue
                all_lines.append(line)
    return all_lines, has_pua


def word_lines_for_pdf(path):
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue
            for line_words in cluster_lines(words):
                texts = segment_line(line_words)
                joined = "".join(texts)
                if not joined.strip():
                    continue
                if is_noise(joined):
                    continue
                lines.append(texts)
    return lines


def parse_questions_gap_based(lines):
    """Fallback parser for plain-text PDFs without PUA glyph markers."""
    questions = []
    mode = "STEM"
    stem_parts = []
    opts = []

    def flush_question():
        nonlocal stem_parts, opts
        text = "".join(stem_parts).strip()
        needs_review = False
        final_opts = opts[:4]
        if len(final_opts) != 4:
            needs_review = True
            while len(final_opts) < 4:
                final_opts.append("")
        if text:
            questions.append({"text": text, "options": final_opts, "needsReview": needs_review})
        stem_parts = []
        opts = []

    for texts in lines:
        n = len(texts)
        if mode == "STEM":
            if n >= 2:
                stem_full = "".join(stem_parts).strip()
                if stem_full:
                    mode = "OPTIONS"
                    opts = list(texts)
                    if len(opts) >= 4:
                        flush_question()
                        mode = "STEM"
                else:
                    stem_parts.append("".join(texts))
            else:
                seg = texts[0]
                stem_parts.append(seg)
                if STEM_END_RE.search(seg):
                    mode = "OPTIONS"
                    opts = []
        else:
            if n == 4:
                opts = list(texts)
            elif n in (1, 2, 3):
                opts.extend(texts)
            if len(opts) >= 4:
                flush_question()
                mode = "STEM"

    return questions


PUA_RUN_RE = re.compile("[-](?:\\s*[-])*")


def parse_questions_glyph_based(lines):
    """Parser for PDFs that mark question/option boundaries with PUA glyphs.

    Different source PDFs embed different custom fonts, so the exact PUA
    codepoint used for "option marker" varies per file (and sometimes all 4
    options reuse the *same* codepoint). The reliable signal is structural,
    not the codepoint value: a *run of 2+ adjacent PUA chars* marks the start
    of a new question, while a *lone* PUA char marks the start of an option.
    """
    full_text = "\n".join(lines)
    runs = list(PUA_RUN_RE.finditer(full_text))
    boundaries = [r for r in runs if len(re.sub(r"\s+", "", r.group())) >= 2]
    questions = []
    for i, m in enumerate(boundaries):
        seg_start = m.end()
        seg_end = boundaries[i + 1].start() if i + 1 < len(boundaries) else len(full_text)
        segment = full_text[seg_start:seg_end]

        marker_positions = [
            (r.start(), r.end()) for r in PUA_RUN_RE.finditer(segment)
            if len(re.sub(r"\s+", "", r.group())) == 1
        ]
        needs_review = False
        if len(marker_positions) < 4:
            needs_review = True
            stem = segment.strip()
            opts = []
        else:
            first4 = marker_positions[:4]
            stem = segment[: first4[0][0]].strip()
            opts = []
            for j in range(4):
                start = first4[j][1]
                end = first4[j + 1][0] if j + 1 < 4 else len(segment)
                opts.append(segment[start:end].strip())
            if len(marker_positions) > 4:
                # extra markers inside option text (rare) — keep as-is, just flag
                needs_review = False

        stem = re.sub(r"\s+", "", stem) if False else stem
        stem = " ".join(stem.split())
        opts = [" ".join(o.split()) for o in opts]
        while len(opts) < 4:
            opts.append("")
            needs_review = True

        if stem:
            questions.append({"text": stem, "options": opts[:4], "needsReview": needs_review})
    return questions


BRACKET_MARKER_RE = re.compile(r"^【(\d)(?:\s*或\s*\d)?】\s*")


def parse_questions_bracket(lines):
    """Parser for PDFs where each question starts with an embedded answer
    marker like 【4】. Some of these files additionally mark options with
    single PUA glyphs; others separate options by column gaps."""
    questions = []
    cur_lines = None
    cur_answer = None

    def flush():
        nonlocal cur_lines, cur_answer
        if cur_lines is None:
            cur_lines = []
            return
        joined = "".join("".join(texts) for texts in cur_lines)
        pua_count = len(ANY_PUA_RE.findall(joined))
        needs_review = False
        if pua_count >= 4:
            parts = ANY_PUA_RE.split(joined)
            # a question-number glyph may sit right at the start
            if parts and not parts[0].strip():
                parts = parts[1:]
            stem = parts[0].strip() if parts else ""
            opts = [p.strip() for p in parts[1:]]
        else:
            stem_parts = []
            opts = []
            mode = "STEM"
            for texts in cur_lines:
                if mode == "STEM":
                    if len(texts) >= 2:
                        mode = "OPTIONS"
                        opts.extend(t.strip() for t in texts)
                    else:
                        seg = texts[0]
                        stem_parts.append(seg)
                        if STEM_END_RE.search(seg):
                            mode = "OPTIONS"
                else:
                    opts.extend(t.strip() for t in texts)
            stem = "".join(stem_parts).strip()
        if len(opts) > 4:
            opts = opts[:3] + ["".join(opts[3:])]
        if len(opts) < 4:
            needs_review = True
            while len(opts) < 4:
                opts.append("")
        if stem:
            questions.append({
                "text": " ".join(stem.split()),
                "options": [" ".join(o.split()) for o in opts[:4]],
                "needsReview": needs_review,
                "embeddedAnswer": cur_answer,
            })
        cur_lines = []
        cur_answer = None

    for texts in lines:
        first = texts[0] if texts else ""
        m = BRACKET_MARKER_RE.match(first.strip())
        if m:
            flush()
            cur_answer = int(m.group(1))
            rest = BRACKET_MARKER_RE.sub("", first.strip(), count=1)
            texts = ([rest] if rest else []) + list(texts[1:])
            if not texts:
                continue
        if cur_lines is None:
            continue  # ignore anything before the first marker (essay section etc.)
        cur_lines.append(texts)
    flush()
    return questions


CATEGORY_MAP = [
    (re.compile(r"原住民"), "原住民特考五等"),
    (re.compile(r"身心障礙|身心特考|身障"), "身心障礙特考五等"),
    (re.compile(r"鐵路.*國安局|國安局.*鐵路"), "鐵路特考佐級／國安局特考五等"),
    (re.compile(r"鐵路"), "鐵路特考佐級"),
    (re.compile(r"關務"), "關務特考五等"),
    (re.compile(r"農田水利會"), "農田水利會招考"),
    (re.compile(r"農田水利署"), "農田水利署招考"),
    (re.compile(r"升官等"), "公務人員升官等考試（薦任）"),
    (re.compile(r"地特三等"), "地方特考三等"),
    (re.compile(r"司法特考四等|執行員"), "司法特考四等"),
    (re.compile(r"初等考試"), "初等考試五等"),
    (re.compile(r"司法"), "司法特考五等"),
]


def derive_meta(filename):
    base = filename.replace(".pdf", "")
    base_clean = base.replace("_unlocked", "")
    m = re.match(r"^(\d{3})\s*年?", base_clean)
    year = int(m.group(1)) if m else None
    rest = base_clean[m.end():] if m else base_clean
    rest = rest.lstrip(" -")
    if "-" in rest:
        cat_part, subject = rest.split("-", 1)
    else:
        cat_part, subject = rest, ""
    cat_part = cat_part.strip(" -")
    subject = subject.strip(" -")

    category = None
    for pat, label in CATEGORY_MAP:
        if pat.search(base_clean):
            category = label
            break
    if category is None:
        category = cat_part or "其他"

    exam_name = f"{year}年公務人員特種考試（{category}）" if year else category
    return year, category, subject or cat_part, exam_name


def main():
    files = sorted(f for f in os.listdir(BASE) if f.lower().endswith(".pdf"))
    total_q = 0
    total_review = 0
    failures = []
    report_lines = []

    for fname in files:
        path = os.path.join(BASE, fname)
        base_name = fname.replace(".pdf", "")
        try:
            lines, has_pua = clean_lines_for_pdf(path)
            n_bracket = sum(1 for ln in lines if BRACKET_MARKER_RE.match(ln.strip()))
            if n_bracket >= 5:
                word_lines = word_lines_for_pdf(path)
                questions = parse_questions_bracket(word_lines)
                parser_used = "bracket"
            elif has_pua:
                questions = parse_questions_glyph_based(lines)
                parser_used = "glyph"
            else:
                word_lines = word_lines_for_pdf(path)
                questions = parse_questions_gap_based(word_lines)
                parser_used = "gap"

            year, category, subject, exam_name = derive_meta(fname)
            for i, q in enumerate(questions, 1):
                q["index"] = i
            n_review = sum(1 for q in questions if q["needsReview"])
            total_q += len(questions)
            total_review += n_review

            doc = {
                "sourceFile": fname,
                "examYear": year,
                "examName": exam_name,
                "examCategory": category,
                "subject": subject,
                "questions": questions,
            }
            out_path = os.path.join(OUT_DIR, base_name + ".json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False)
            report_lines.append(f"{fname}: {len(questions)} 題（{parser_used}，待覆核 {n_review}）")
        except Exception as e:
            failures.append((fname, str(e)))
            report_lines.append(f"{fname}: FAILED - {e}")

    report_path = r"D:\OneDrive - ncut.edu.tw\國立勤益科技大學\系統開發\司法五等-20260716T010343Z-1-001\data\extraction_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 題目擷取報告\n\n共處理 {len(files)} 份檔案，共擷取 {total_q} 題，其中 {total_review} 題待人工覆核，失敗 {len(failures)} 份。\n\n")
        for line in report_lines:
            f.write(f"- {line}\n")

    print(f"Processed {len(files)} files, {total_q} questions, {total_review} needsReview, {len(failures)} failures")
    for fname, err in failures:
        print("FAILED:", fname, err)


if __name__ == "__main__":
    main()
