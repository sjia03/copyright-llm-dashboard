"""Research Progress dashboard, native Streamlit port.

This does NOT run the live dashboard -- that needs local, multi-GB result
files and a running Python backend that can't live in a public repo. It
reads a frozen JSON export (dashboard_data.json) and renders it with native
Streamlit/Plotly widgets instead of embedding the standalone HTML page, so it
picks up Streamlit's own layout, width, and light/dark theming rather than
sitting in a separate scrolling iframe.

To refresh: regenerate dashboard_data.json from the local dashboard and push
the update -- Streamlit Cloud redeploys automatically on push.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Research Progress", page_icon="📊", layout="wide")

DATA_PATH = Path(__file__).parent / "dashboard_data.json"

TASK_LABELS = {
    "name-cloze": "Name Cloze",
    "concept-test": "Concept Test",
    "text-extraction": "Text Extraction",
    "books3-demand": "Books3 Demand",
    "revision-tracker": "Revision Tracker",
}

@st.cache_data
def load_data():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Filtering pipeline / summary stats / raw Books3 comparison
# ---------------------------------------------------------------------------

def render_funnel(funnel):
    st.subheader("Filtering pipeline")
    df = pd.DataFrame(funnel)
    show_cols = ["step", "remaining", "filter_type", "why"]
    df = df[show_cols].rename(columns={
        "step": "Step", "remaining": "Remaining", "filter_type": "Filter type", "why": "Why it matters",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)

    excluded = [f for f in funnel if f.get("excluded_genres")]
    for f in excluded:
        with st.expander(f"{len(f['excluded_genres'])} genres excluded at “{f['step']}”"):
            st.write(", ".join(f["excluded_genres"]))


def render_summary_stats(summary_stats):
    if not summary_stats:
        return
    st.subheader("Sample summary statistics")
    title_map = {
        "full_corpus_n12916": "Full corpus (12,916 books)",
        "restricted_sample_n494": "Restricted sample (494 books)",
        "current_sample": "Current sample",
        "full_bank": "Full bank",
        "matched_sample_n8124": "Matched checkout sample (8,124 books)",
    }
    cols = st.columns(2)
    for i, (key, rows) in enumerate(summary_stats.items()):
        with cols[i % 2]:
            st.markdown(f"**{title_map.get(key, key)}**")
            if not rows:
                st.caption("No books in this scope.")
                continue
            df = pd.DataFrame(rows).rename(columns={"category": "Category", "trait": "Trait", "n": "N", "pct": "%"})
            st.dataframe(df, use_container_width=True, hide_index=True)


def raw3_row(r, label, tier_or_outcome):
    raw = r
    if not raw or raw.get("in_books3_mean") is None or raw.get("not_books3_mean") is None:
        return {"Model": label, "": tier_or_outcome, "In Books3": "—", "Not in Books3": "—", "Diff": "—"}
    diff = raw.get("diff")
    diff_str = "—" if diff is None else f"{'+' if diff >= 0 else ''}{diff * 100:.1f} pp"
    return {
        "Model": label,
        "": tier_or_outcome,
        "In Books3": f"{raw['in_books3_mean'] * 100:.1f}% (n={raw['in_books3_n']:,})",
        "Not in Books3": f"{raw['not_books3_mean'] * 100:.1f}% (n={raw['not_books3_n']:,})",
        "Diff": diff_str,
    }


def render_books3_raw_table(task_id, data):
    results = data.get("results", [])
    rows = []
    if task_id == "name-cloze":
        for r in results:
            rows.append(raw3_row(r.get("books3_raw"), r["model"], r.get("tier", "")))
    else:
        for r in results:
            for o in r.get("outcomes", []):
                rows.append(raw3_row(o.get("books3_raw"), r["model"], o.get("outcome", "")))
    if not rows:
        return
    st.subheader("Raw average scores: Books3 vs. non-Books3")
    df = pd.DataFrame(rows)
    label_col = "Tier" if task_id == "name-cloze" else "Outcome"
    df = df.rename(columns={"": label_col})
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        "Unconditional group means -- no regression, no controls, no clustering, just the plain average "
        "score in each group. Diff = In-Books3 mean minus Not-in-Books3 mean, in percentage points. "
        "See the regression table below for the IV-identified estimate."
    )


# ---------------------------------------------------------------------------
# Regression results table
# ---------------------------------------------------------------------------

SPEC_LABELS = ["OLS", "IV", "IV + pop FE", "IV + pop FE + controls"]


def spec_cell(spec):
    if not spec:
        return "—"
    return f"{spec['coef']:.4f}{spec.get('stars', '')} ({spec['se']:.4f})"


def regression_row(label, tier_or_outcome, status, n_books, n_items, regressions):
    row = {"Model": label, "": tier_or_outcome, "Status": status, "Books": n_books, "Items": n_items}
    if not regressions or not regressions.get("ok"):
        reason = (regressions or {}).get("reason", "no data")
        for s in SPEC_LABELS:
            row[s] = f"insufficient data ({reason})" if s == "OLS" else ""
        return row
    by_label = {s["label"]: s for s in regressions["specs"]}
    for s in SPEC_LABELS:
        row[s] = spec_cell(by_label.get(s))
    return row


def render_regression_table(task_id, data):
    results = data.get("results", [])
    rows = []
    if task_id == "name-cloze":
        for r in results:
            rows.append(regression_row(
                r["model"], r.get("tier", ""), r.get("status", ""),
                r.get("n_books"), r.get("n_items"), r.get("regressions"),
            ))
    else:
        outcome_key = "metrics" if task_id == "text-extraction" else "outcomes"
        for r in results:
            items = r.get(outcome_key, [])
            if not items:
                rows.append({"Model": r["model"], "": "", "Status": r.get("status", ""), "Books": None, "Items": None,
                             **{s: "" for s in SPEC_LABELS}})
                continue
            for o in items:
                rows.append(regression_row(
                    r["model"], o.get("outcome") or o.get("metric", ""), r.get("status", ""),
                    o.get("n_books"), o.get("n_items"), o.get("regressions"),
                ))
    if not rows:
        return
    st.subheader("Raw results & regressions")
    df = pd.DataFrame(rows)
    label_col = "Tier" if task_id == "name-cloze" else ("Metric" if task_id == "text-extraction" else "Outcome")
    df = df.rename(columns={"": label_col})
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        "Regression spec ladder: (1) OLS score ~ books3. (2) IV: books3 instrumented by shares "
        "(books3's publication-year composition). (3) adds popularity-bucket fixed effects. (4) adds "
        "num_reviews / num_ratings / avg_rating controls. Robust (HC1) SEs throughout; "
        "stars: * p<.10, ** p<.05, *** p<.01."
    )


# ---------------------------------------------------------------------------
# Visuals: coefficient/forest plot + per-model pub-year trend small multiples
# ---------------------------------------------------------------------------

def headline_spec(regressions):
    if not regressions or not regressions.get("ok"):
        return None
    spec = next((s for s in regressions["specs"] if s["label"] == "IV + pop FE + controls"), None)
    if not spec or spec.get("se") is None:
        return None
    ci = 1.96 * spec["se"]
    return {
        "coef": spec["coef"], "se": spec["se"],
        "lo": spec["coef"] - ci, "hi": spec["coef"] + ci,
        "p": spec["p"], "n": spec["n"], "sig": spec["p"] < 0.05,
    }


def coefficient_plot_rows(task_id, data):
    results = data.get("results", [])
    rows = []
    if task_id == "name-cloze":
        for r in results:
            h = headline_spec(r.get("regressions"))
            if h:
                rows.append({"label": r["model"], **h})
    else:
        for r in results:
            for o in r.get("outcomes", []):
                h = headline_spec(o.get("regressions"))
                if h:
                    rows.append({"label": f"{r['model']} — {o['outcome']}", **h})
    return rows


def render_coefficient_plot(task_id, data):
    rows = coefficient_plot_rows(task_id, data)
    if not rows:
        return
    rows = rows[::-1]  # plotly lists categorical y top-to-bottom in reverse insertion order
    labels = [r["label"] for r in rows]
    coefs = [r["coef"] for r in rows]
    err_hi = [r["hi"] - r["coef"] for r in rows]
    err_lo = [r["coef"] - r["lo"] for r in rows]
    colors = ["#2382c9" if r["sig"] else "rgba(35,130,201,0)" for r in rows]
    line_colors = ["#2382c9"] * len(rows)
    hover = [
        f"{r['label']}<br>coef {r['coef']:.4f} (SE {r['se']:.4f})<br>95% CI [{r['lo']:.4f}, {r['hi']:.4f}]<br>N={r['n']:,}"
        for r in rows
    ]

    fig = go.Figure()
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(120,120,120,0.6)")
    fig.add_trace(go.Scatter(
        x=coefs, y=labels, mode="markers",
        marker=dict(size=10, color=colors, line=dict(color=line_colors, width=2)),
        error_x=dict(type="data", symmetric=False, array=err_hi, arrayminus=err_lo, color="rgba(120,120,120,0.7)", thickness=1.5),
        hovertext=hover, hoverinfo="text",
    ))
    fig.update_layout(
        height=max(220, 34 * len(rows) + 60),
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False,
        xaxis_title="Coefficient (IV + pop FE + controls)",
        template="plotly_white",
    )
    st.subheader("All models at a glance: headline coefficient")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Coefficient ± 95% CI from the IV + pop FE + controls spec (the regression table's spec 4). "
        "Filled dot = significant at p<.05; hollow = not. Dashed line = zero (no effect)."
    )


def pub_year_trend_cards(task_id, data):
    results = data.get("results", [])
    cards = []
    if task_id == "name-cloze":
        for r in results:
            pts = r.get("pub_year_trend") or []
            if len(pts) >= 3:
                cards.append({"title": r["model"], "points": pts})
    else:
        for r in results:
            for o in r.get("outcomes", []):
                pts = o.get("pub_year_trend") or []
                if len(pts) >= 3:
                    cards.append({"title": f"{r['model']} — {o['outcome']}", "points": pts})
    return cards


def render_pub_year_trend_grid(task_id, data):
    cards = pub_year_trend_cards(task_id, data)
    if not cards:
        return
    st.subheader("Score by publication year, per model")

    n_cols = 4
    n_rows = -(-len(cards) // n_cols)  # ceil division
    fig = make_subplots(
        rows=n_rows, cols=n_cols,
        subplot_titles=[c["title"] for c in cards],
        vertical_spacing=0.12 / max(n_rows, 1), horizontal_spacing=0.04,
    )
    for i, c in enumerate(cards):
        row, col = i // n_cols + 1, i % n_cols + 1
        years = [p["pub_year"] for p in c["points"]]
        means = [p["mean"] for p in c["points"]]
        hover = [f"{p['pub_year']}: {p['mean'] * 100:.1f}% (n={p['n']})" for p in c["points"]]
        fig.add_trace(go.Scatter(
            x=years, y=means, mode="lines", line=dict(color="#2382c9", width=2),
            fill="tozeroy", fillcolor="rgba(35,130,201,0.10)",
            hovertext=hover, hoverinfo="text", showlegend=False,
        ), row=row, col=col)
        for ref_year in (2012, 2020):
            if min(years) <= ref_year <= max(years):
                fig.add_vline(x=ref_year, line_dash="dash", line_color="rgba(120,120,120,0.5)", row=row, col=col)
        fig.update_yaxes(tickformat=".0%", row=row, col=col)

    fig.update_layout(
        height=210 * n_rows, margin=dict(l=10, r=10, t=40, b=10),
        template="plotly_white",
    )
    fig.update_annotations(font_size=11)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Mean score by publication year (books published before 2000 excluded). Dashed lines mark 2012 "
        "and 2020, the same reference years used in tables/scatter_<model>.pdf's Stata figures -- watch "
        "for a level shift right around them. Each chart has its own y-axis (baselines differ a lot by "
        "model); hover a point for the exact year/n."
    )


# ---------------------------------------------------------------------------
# Books3 demand tab (different shape: no per-model results, a fixed comparison)
# ---------------------------------------------------------------------------

def demand_cell(cell):
    if not cell:
        return "—"
    stars = "***" if cell.get("p") is not None and cell["p"] < 0.01 else \
        "**" if cell.get("p") is not None and cell["p"] < 0.05 else \
        "*" if cell.get("p") is not None and cell["p"] < 0.10 else ""
    parts = [f"{cell['coef']:+.4f}{stars} ({cell['se']:.4f})"]
    if cell.get("f_stat") is not None:
        parts.append(f"F={cell['f_stat']:.1f}")
    if cell.get("ci_lower") is not None:
        parts.append(f"95% CI [{cell['ci_lower']:.4f}, {cell['ci_upper']:.4f}]")
    if cell.get("n_books") is not None:
        parts.append(f"N={cell['n_books']:,}")
    return " | ".join(parts)


def render_books3_demand(data):
    if data.get("error"):
        st.error(data["error"])
        return
    if data.get("headline"):
        st.info(f"**Headline:** {data['headline']}")

    st.subheader("Keepa sales rank vs. SPL checkout demand")
    rows = []
    for r in data.get("comparison", []):
        rows.append({
            "Estimator": r["spec"],
            "Keepa (sales rank)": demand_cell(r.get("keepa")),
            "SPL checkouts": demand_cell(r.get("checkout")),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Keepa: + = sells worse post-ChatGPT (substitution-consistent). SPL checkouts: + = more "
        "checkouts post-ChatGPT. Robust/clustered SEs. Stars: * p<.10, ** p<.05, *** p<.01. "
        "CS-DiD ATT has no p-value -- read significance off the 95% CI."
    )

    outcomes = data.get("outcomes", [])
    equations = data.get("equations", [])
    if outcomes:
        st.subheader("How the outcome variable was constructed")
        for o in outcomes:
            with st.expander(o["source"]):
                st.write(o["text"])
    if equations:
        st.subheader("Regression equations")
        for e in equations:
            with st.expander(e["label"]):
                st.markdown(e["equation"], unsafe_allow_html=True)
                st.caption(e["note"])


# ---------------------------------------------------------------------------
# Revision tracker (curated content from the R&R reviews, not eval data)
# ---------------------------------------------------------------------------

PRIORITY_COLOR = {"critical": "red", "suggested": "gray"}
PRIORITY_LABEL = {"critical": "Critical", "suggested": "Suggested"}


def status_color(status):
    s = (status or "").lower()
    if "progress" in s:
        return "blue"
    if "done" in s or "complete" in s:
        return "green"
    return "gray"


def render_tracker_item(item):
    with st.container(border=True):
        st.markdown(f"**{item['title']}**")
        badges = [f":{PRIORITY_COLOR.get(item['priority'], 'gray')}-badge[{PRIORITY_LABEL.get(item['priority'], item['priority'])}]"]
        badges.append(f":{status_color(item.get('status'))}-badge[{item.get('status', '')}]")
        badges += [f":violet-badge[{r}]" for r in item.get("reviewers", [])]
        st.markdown(" ".join(badges))
        st.write(item["description"])
        if item.get("notes"):
            st.info(f"**Notes:** {item['notes']}", icon="📝")


def render_revision_tracker(data):
    d = data.get("decision", {})
    header = f"**{d.get('outcome', '')}**"
    if d.get("date"):
        header += f" — {d['date']}"
    if d.get("editor"):
        header += f" ({d['editor']})"
    st.warning(f"{header}\n\n{d.get('summary', '')}", icon="⚠️")

    for cat in data.get("categories", []):
        items = cat.get("items", [])
        st.subheader(f"{cat['label']} ({len(items)})")
        st.caption(cat.get("description", ""))
        if not items:
            st.caption("No items in this category.")
            continue
        for item in items:
            render_tracker_item(item)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def render_task(task_id, data):
    if task_id == "revision-tracker":
        render_revision_tracker(data)
        return

    note = data.get("note") or data.get("excluded_note")
    render_funnel(data.get("funnel", []))
    if note:
        st.caption(note)
    render_summary_stats(data.get("summary_stats", {}))

    if task_id == "books3-demand":
        render_books3_demand(data)
        return

    show_extras = task_id in ("name-cloze", "concept-test")
    if show_extras:
        render_books3_raw_table(task_id, data)
    render_regression_table(task_id, data)
    if show_extras:
        render_coefficient_plot(task_id, data)
        render_pub_year_trend_grid(task_id, data)


def main():
    data = load_data()

    st.title("\U0001F4CA Research Progress")
    st.caption(f"Static snapshot -- captured {data.get('_captured_at', 'unknown')}. Not live.")

    task_ids = [t for t in TASK_LABELS if t in data]
    tabs = st.tabs([TASK_LABELS[t] for t in task_ids])
    for tab, task_id in zip(tabs, task_ids):
        with tab:
            render_task(task_id, data[task_id])


if __name__ == "__main__":
    main()
