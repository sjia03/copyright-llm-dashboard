# Research Progress — Dashboard Snapshot

A static, self-contained snapshot of a research dashboard tracking four LLM-memorization
eval tasks (name-cloze, concept-test, character-test, text-extraction) plus a Books3
sales-demand comparison, for a paper on the economics of copyright and LLMs.

This is **not live** — the real dashboard reads local, multi-GB result files and runs
regressions on demand, which can't run in a public deployment. `research_dashboard_snapshot.html`
is a frozen export of that page's output; `app.py` just embeds it in a Streamlit page so it's
easy to share a link to.

To refresh with new results: regenerate `research_dashboard_snapshot.html` from the local
dashboard and push the update — Streamlit Cloud redeploys automatically on push.
