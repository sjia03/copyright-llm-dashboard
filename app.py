"""Streamlit wrapper around the research-progress dashboard.

This does not run the live dashboard (that needs local, multi-GB result
files and a running Python backend that can't live in a public repo). It
instead embeds a static, self-contained snapshot of the same page -- the
funnel tables, model results, and regressions are frozen at export time.
To refresh: regenerate research_dashboard_snapshot.html from the local
dashboard and push the update; Streamlit Cloud redeploys automatically.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Research Progress — Snapshot", page_icon="📊", layout="wide")

html_path = Path(__file__).parent / "research_dashboard_snapshot.html"
html = html_path.read_text(encoding="utf-8")

components.html(html, height=2600, scrolling=True)
