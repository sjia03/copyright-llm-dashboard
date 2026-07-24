# Research Progress — Dashboard

A native Streamlit rendering of a research dashboard tracking three LLM-memorization
eval tasks (name-cloze, concept-test, text-extraction) plus a Books3 sales-demand
comparison, for a paper on the economics of copyright and LLMs.

This is **not live** — the real dashboard reads local, multi-GB result files and runs
regressions on demand, which can't run in a public deployment. `dashboard_data.json`
is a frozen export of that data; `app.py` renders it with native Streamlit + Plotly
widgets (tabs, dataframes, charts) rather than embedding a static HTML page, so it
picks up Streamlit's own layout/width/theme instead of sitting in a separate
scrolling iframe.

To refresh with new results: regenerate `dashboard_data.json` from the local
dashboard and push the update — Streamlit Cloud redeploys automatically on push.
