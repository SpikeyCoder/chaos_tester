#!/usr/bin/env python3
"""
Audit every inline `style="..."` attribute under chaos_tester/templates/.

Output: a markdown report categorizing every occurrence as
  - static-class       (no Jinja interpolation; deterministic; refactor to CSS class)
  - dynamic-property   (contains {{ ... }} or {% ... %}; refactor to CSS custom property + class)
  - one-off            (rare unique value used <=1 times; visual review on case-by-case basis)

The report is intended to size the work for chaos_tester pen-test finding
WA-2026-05-05-02 (drop 'unsafe-inline' from CSP style-src).
"""

import os
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

TEMPLATE_DIR = sys.argv[1] if len(sys.argv) > 1 else "templates"
STYLE_RE = re.compile(r'style="([^"]+)"')
JINJA_RE = re.compile(r"\{\{|\{%|\{#")


def normalize(style):
    """Stable string for grouping equivalent styles together."""
    parts = [p.strip() for p in style.split(";") if p.strip()]
    parts.sort()
    return "; ".join(parts)


def categorize(style):
    if JINJA_RE.search(style):
        return "dynamic-property"
    return "static"


def declarations(style):
    out = []
    for part in style.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        prop, _, value = part.partition(":")
        out.append((prop.strip().lower(), value.strip()))
    return out


def suggest_class_name(style):
    """Tiny heuristic for an initial class-name suggestion. Manual review still required."""
    decls = declarations(style)
    props = sorted({p for p, _ in decls})
    # severity / status pills
    s = style.lower()
    if "background:rgba(74,222,128" in s or "color:#4ade80" in s:
        return ".badge-success"
    if "background:rgba(248,113,113" in s or "color:#f87171" in s:
        return ".badge-danger"
    if "background:rgba(251,191,36" in s or "color:#fbbf24" in s:
        return ".badge-warning"
    if "background:rgba(96,165,250" in s or "color:#60a5fa" in s:
        return ".badge-info"
    if "background:rgba(167,139,250" in s or "color:#a78bfa" in s:
        return ".badge-purple"
    if "background:rgba(244,114,182" in s or "color:#f472b6" in s:
        return ".badge-pink"
    # screen-reader-only sentinel
    if (
        "position:absolute" in s
        and "width:1px" in s
        and "height:1px"
    ):
        return ".sr-only"
    # display utilities
    if props == ["display"]:
        v = decls[0][1]
        return f".u-display-{v.replace(' ', '-')}"
    # background:none button reset
    if "background:none" in s and "border:none" in s:
        return ".btn-reset"
    # surface card
    if "background:var(--surface" in s and "border-radius" in s and "padding" in s:
        return ".card"
    # alert info
    if (
        "background:rgba(59,130,246" in s
        and "border-left:4px solid" in s
    ):
        return ".alert-info"
    if "background:#fef3c7" in s and "border:1px solid #fcd34d" in s:
        return ".alert-warning"
    # divider / border-left status cards
    if "border-left:4px solid" in s and "padding:16px" in s:
        return ".status-card"
    # default
    return f".u-{'-'.join(props[:3])}"


def main():
    root = Path(TEMPLATE_DIR)
    files = sorted(p for p in root.rglob("*.html"))

    findings = []
    by_template = defaultdict(int)
    by_category = Counter()
    by_normalized_static = Counter()
    by_normalized_dynamic = Counter()
    suggested_class_for = {}

    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in STYLE_RE.finditer(text):
            raw = m.group(1)
            norm = normalize(raw)
            cat = categorize(raw)
            line = text.count("\n", 0, m.start()) + 1
            findings.append({
                "file": str(f.relative_to(root.parent)),
                "line": line,
                "raw": raw,
                "norm": norm,
                "category": cat,
            })
            by_template[str(f.relative_to(root.parent))] += 1
            by_category[cat] += 1
            if cat == "static":
                by_normalized_static[norm] += 1
                suggested_class_for[norm] = suggest_class_name(raw)
            else:
                by_normalized_dynamic[norm] += 1

    total = len(findings)
    static_count = by_category["static"]
    dynamic_count = by_category["dynamic-property"]
    unique_static = len(by_normalized_static)
    unique_dynamic = len(by_normalized_dynamic)
    one_off_static = sum(1 for n, c in by_normalized_static.items() if c == 1)

    out = []
    out.append("---")
    out.append("title: Inline-style audit (chaos_tester templates)")
    out.append("tsc: CC6.1, CC8.1")
    out.append("owner: Kevin Armstrong")
    out.append("review-cadence: ad-hoc (refresh after each refactor PR)")
    out.append("last-reviewed: 2026-05-05")
    out.append("---")
    out.append("")
    out.append("# Inline-style audit — chaos_tester templates")
    out.append("")
    out.append(
        "This document sizes the **WA-2026-05-05-02** remediation work — dropping "
        "`'unsafe-inline'` from the `style-src` CSP directive in `app.py`. Generated "
        "by `scripts/audit_inline_styles.py` against `templates/`."
    )
    out.append("")
    out.append("## 1. Headline numbers")
    out.append("")
    out.append("| Metric | Count |")
    out.append("|---|---:|")
    out.append(f"| Total inline `style=` attributes | {total} |")
    out.append(f"| Static (no Jinja interpolation) | {static_count} |")
    out.append(f"| Dynamic (template-interpolated) | {dynamic_count} |")
    out.append(f"| Unique normalized static values | {unique_static} |")
    out.append(f"| Unique normalized dynamic values | {unique_dynamic} |")
    out.append(f"| Static one-offs (used exactly once) | {one_off_static} |")
    out.append("")
    out.append(
        f"**Read of the numbers**: {static_count} of the {total} inline styles are "
        f"static, but they collapse into only ~{unique_static} unique values — meaning "
        f"a focused class library of roughly that size covers the entire static surface. "
        f"The {dynamic_count} dynamic styles all need CSS custom properties + a class; "
        f"there are only ~{unique_dynamic} distinct shapes to handle there."
    )
    out.append("")

    out.append("## 2. Per-template density")
    out.append("")
    out.append("| Template | Count |")
    out.append("|---|---:|")
    for tpl, count in sorted(by_template.items(), key=lambda x: -x[1]):
        out.append(f"| `{tpl}` | {count} |")
    out.append("")

    out.append("## 3. Top static patterns (refactor priority)")
    out.append("")
    out.append(
        "Sorted by occurrence count. The highest-count rows are the ones whose "
        "class-ification deletes the most inline styles per unit of effort."
    )
    out.append("")
    out.append("| Count | Suggested class | Normalized style |")
    out.append("|---:|---|---|")
    top_static = sorted(by_normalized_static.items(), key=lambda x: -x[1])[:25]
    for norm, count in top_static:
        cls = suggested_class_for.get(norm, "?")
        # truncate aggressive long values
        display = norm if len(norm) < 110 else norm[:107] + "..."
        out.append(f"| {count} | `{cls}` | `{display}` |")
    out.append("")

    out.append("## 4. Dynamic-style shapes (need CSS custom properties)")
    out.append("")
    out.append(
        "Each row is a unique template-interpolated style. The remediation is the "
        "same shape for every row: replace `{{ value }}` with a CSS custom property "
        "and add a class that consumes it."
    )
    out.append("")
    out.append("| Count | Normalized style |")
    out.append("|---:|---|")
    top_dynamic = sorted(by_normalized_dynamic.items(), key=lambda x: -x[1])[:30]
    for norm, count in top_dynamic:
        display = norm if len(norm) < 130 else norm[:127] + "..."
        out.append(f"| {count} | `{display}` |")
    out.append("")
    if len(by_normalized_dynamic) > 30:
        out.append(
            f"_({len(by_normalized_dynamic) - 30} more dynamic shapes omitted; rerun "
            f"the audit script for the full list.)_"
        )
        out.append("")

    out.append("## 5. Refactor strategy")
    out.append("")
    out.append("**Phase 1 — class library (`static/report.css`)**")
    out.append("")
    out.append(
        "- Pick the top 25 patterns from §3 and write them as utility classes. Each one "
        "deletes between 1 and ~30 inline-style occurrences."
    )
    out.append(
        "- Group by intent: `.badge-{success,danger,warning,info,purple,pink}`, "
        "`.alert-{info,warning,danger}`, `.card`, `.card-flat`, `.status-card`, `.btn-reset`, "
        "`.sr-only`, `.u-display-{none,grid,flex}`, severity-pill family, alert family."
    )
    out.append(
        "- Author the class library in one commit; it ships a stylesheet but does not "
        "touch any template, so it is safe to merge ahead of the template edits."
    )
    out.append("")
    out.append("**Phase 2 — template-by-template substitution**")
    out.append("")
    out.append(
        "- Replace inline static `style=\"...\"` attributes with the corresponding "
        "class. Refactor in priority order: `sample_report.html`, `report.html`, "
        "`dashboard.html`, then the long tail."
    )
    out.append(
        "- Visual regression after each template ships: capture Playwright screenshots "
        "of `/sample-report` and a representative `/report/<run_id>` and diff against the "
        "baseline. The report renderer is a single Jinja path (`render_template('report.html', ...)`), "
        "so there is no second renderer to keep in sync."
    )
    out.append("")
    out.append("**Phase 3 — dynamic-style refactor**")
    out.append("")
    out.append(
        "- For each row in §4, replace the interpolated style with a CSS custom "
        "property + class. Example:"
    )
    out.append("")
    out.append("```html")
    out.append("<!-- before -->")
    out.append('<div style="border-left:4px solid {{ pdata.color }};">...</div>')
    out.append("")
    out.append("<!-- after -->")
    out.append('<div class="status-card" style="--status-color: {{ pdata.color }};">...</div>')
    out.append("```")
    out.append("")
    out.append("```css")
    out.append("/* static/report.css */")
    out.append(".status-card {")
    out.append("  border-left: 4px solid var(--status-color);")
    out.append("  padding: 16px;")
    out.append("  border-radius: 8px;")
    out.append("}")
    out.append("```")
    out.append("")
    out.append(
        "Note: the **value** of `--status-color` is still interpolated, but it is now "
        "a single token (a hex / rgb color) instead of a full CSS declaration. A future "
        "CSP move to drop `style-src-attr 'unsafe-inline'` would still need an allowlist "
        "for these inline custom-property assignments — see Phase 5."
    )
    out.append("")
    out.append("**Phase 4 — drop `'unsafe-inline'` from `style-src`**")
    out.append("")
    out.append(
        "- Update `app.py:131` once Phases 2 and 3 are done. Verify no CSP violations on "
        "every Flask route. Add a CI grep that fails any future PR that introduces a `style=` "
        "attribute under `templates/`."
    )
    out.append("")
    out.append("**Phase 5 — (stretch) split into `style-src-elem` / `style-src-attr`**")
    out.append("")
    out.append(
        "- After Phase 4, optionally split the directive: `style-src-elem 'self'; "
        "style-src-attr 'self' 'unsafe-hashes' <hashes>`. This keeps the `--status-color` "
        "inline assignments working under explicit hashes rather than blanket "
        "`'unsafe-inline'`."
    )
    out.append("")

    out.append("## 6. Effort estimate")
    out.append("")
    out.append("| Phase | Days |")
    out.append("|---|---:|")
    out.append("| 1 — class library | 1 |")
    out.append("| 2 — template substitution (sample_report.html, report.html) | 2.5 |")
    out.append("| 2 — template substitution (dashboard.html, progress.html, long tail) | 1.5 |")
    out.append("| 3 — dynamic-style refactor | 1 |")
    out.append("| 4 — drop `'unsafe-inline'` + CI guard + final regression test | 1 |")
    out.append("| 5 — (optional) split-directive hardening | 0.5 |")
    out.append("| **Total** | **7–8 days** |")
    out.append("")

    out.append("## 7. Provenance")
    out.append("")
    out.append(
        "Generated by `scripts/audit_inline_styles.py templates/`. Re-run any time "
        "after a template edit to see how the numbers move; the script is deterministic "
        "and stdout-only."
    )

    print("\n".join(out))


if __name__ == "__main__":
    main()
