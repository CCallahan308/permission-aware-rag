"""CGC Labs presentation helpers for the synthetic Streamlit demonstration."""

import base64
from html import escape
from pathlib import Path
import re
from typing import Mapping

import streamlit as st


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "docs" / "assets"


def inject_brand_styles() -> None:
    st.markdown(
        """<style>
        @import url('https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@800&display=swap');
        @import url('https://api.fontshare.com/v2/css?f[]=general-sans@400,500,600&display=swap');
        :root {--cgc-canvas:#f6f8f4;--cgc-soft:#eaf0e9;--cgc-ink:#142b24;
          --cgc-muted:#526259;--cgc-rule:#d3ddd4;--cgc-lime:#d5f36b;}
        html,body,[data-testid="stAppViewContainer"],[data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],input,textarea,button {font-family:'General Sans',Arial,sans-serif;}
        .stApp,[data-testid="stAppViewContainer"] {background:var(--cgc-canvas);color:var(--cgc-ink);}
        [data-testid="stHeader"] {background:var(--cgc-canvas);}
        [data-testid="stMainBlockContainer"] {max-width:1320px;padding:5.5rem 3rem 2rem;}
        h1,h2,h3,h4 {font-family:'Cabinet Grotesk',Arial,sans-serif!important;
          font-weight:800!important;letter-spacing:-.04em!important;color:var(--cgc-ink);}
        h2 {font-size:2rem!important;}h3 {font-size:1.5rem!important;}
        p,li {line-height:1.65;}
        a {color:var(--cgc-ink);text-underline-offset:4px;}
        a:focus-visible,button:focus-visible {outline:3px solid #637d18!important;outline-offset:4px;}
        ::selection {background:var(--cgc-lime);color:var(--cgc-ink);}
        .cgc-header {display:flex;align-items:center;justify-content:space-between;gap:24px;
          padding:0 0 24px;border-bottom:1px solid var(--cgc-rule);}
        .cgc-logo {display:inline-flex;align-items:center;min-height:44px;}
        .cgc-logo img {display:block;width:110px;height:auto;}
        .cgc-header-note {font-size:12px;color:var(--cgc-muted);text-align:right;line-height:1.6;}
        .cgc-header-note a {display:inline-flex;align-items:center;min-height:44px;text-decoration:none;}
        .stApp .cgc-header a,.stApp .cgc-foot a {color:var(--cgc-ink)!important;}
        .cgc-hero {display:grid;grid-template-columns:1.12fr 1fr;gap:48px;align-items:end;padding:38px 0 32px;}
        .cgc-label {font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--cgc-muted);}
        .cgc-hero h1 {font-size:clamp(48px,5.6vw,76px)!important;line-height:1.02!important;
          letter-spacing:-.055em!important;margin:12px 0 0!important;padding:0!important;}
        .cgc-accent {position:relative;display:inline-block;isolation:isolate;}
        .cgc-accent:after {content:'';position:absolute;z-index:-1;left:0;right:0;bottom:.06em;
          height:.2em;background:var(--cgc-lime);}
        .cgc-hero-copy {padding-bottom:4px;max-width:450px;}
        .cgc-hero-copy p {font-size:18px;line-height:1.6;color:var(--cgc-muted);margin:0 0 12px;}
        .cgc-hero-copy small {font-size:12px;color:var(--cgc-muted);}
        button[kind="primary"] {background:var(--cgc-ink)!important;color:white!important;
          border:1px solid var(--cgc-ink)!important;border-radius:4px!important;min-height:48px;}
        button[kind="secondary"],button[kind="tertiary"] {min-height:44px;border-radius:4px!important;}
        [data-testid="stBaseButton-primary"]:hover {background:#2e4a3f!important;}
        [data-baseweb="tab-list"] {gap:28px;border-bottom:1px solid var(--cgc-rule);}
        [data-baseweb="tab"] {height:54px;padding-inline:0;font-family:'General Sans',Arial,sans-serif;}
        [data-baseweb="tab-highlight"] {background:var(--cgc-ink)!important;height:2px;}
        [data-testid="stTabs"] [data-baseweb="tab-panel"] {padding-top:28px;}
        [data-testid="stSelectbox"]>label,[data-testid="stTextInput"]>label,
        [data-testid="stSlider"]>label {color:var(--cgc-ink);font-size:13px;font-weight:500;}
        [data-baseweb="select"]>div,[data-baseweb="input"] {background:white;border-color:var(--cgc-rule);border-radius:4px;}
        [data-testid="stExpander"] {border-color:var(--cgc-rule);border-radius:0;}
        [data-testid="stExpander"] summary {min-height:48px;}
        [data-testid="stCaptionContainer"] {color:var(--cgc-muted);}
        .cgc-section-title {border-top:1px solid var(--cgc-rule);padding-top:22px;margin:8px 0 18px;}
        .cgc-empty {padding:26px 28px;background:var(--cgc-soft);min-height:190px;}
        .cgc-empty h2 {margin:10px 0 14px!important;padding:0!important;}
        .cgc-empty p {margin:0;max-width:480px;color:var(--cgc-muted);font-size:15px;}
        .cgc-answer {padding:26px 0;border-top:1px solid var(--cgc-rule);border-bottom:1px solid var(--cgc-rule);}
        .cgc-answer-text {font-size:21px;line-height:1.7;white-space:pre-line;overflow-wrap:anywhere;}
        .cgc-citation {display:inline-block;padding:1px 7px;margin:0 2px;background:var(--cgc-soft);
          font-size:11px;font-weight:600;white-space:nowrap;vertical-align:middle;}
        .cgc-status {display:inline-flex;align-items:center;gap:8px;margin-bottom:14px;
          font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;}
        .cgc-status:before {content:'';width:7px;height:7px;background:var(--cgc-ink);}
        .cgc-result-facts {margin:14px 0 22px;color:var(--cgc-muted);font-size:12px;line-height:1.8;}
        .cgc-source-text {font-size:15px;line-height:1.75;white-space:pre-line;color:var(--cgc-ink);overflow-wrap:anywhere;}
        .cgc-permissions {font-size:12px;color:var(--cgc-muted);margin:12px 0 0;}
        .cgc-figure {width:100%;overflow-x:auto;border:1px solid var(--cgc-rule);background:var(--cgc-canvas);}
        .cgc-figure img {display:block;width:100%;min-width:760px;height:auto;}
        .cgc-foot {display:flex;align-items:center;justify-content:space-between;gap:24px;
          margin-top:34px;padding-top:24px;border-top:1px solid var(--cgc-rule);font-size:12px;color:var(--cgc-muted);}
        .cgc-foot a {display:inline-flex;align-items:center;min-height:44px;}
        @media(max-width:850px) {
          [data-testid="stMainBlockContainer"] {padding:5.3rem 1.5rem 1.5rem;}
          .cgc-hero {grid-template-columns:1fr;gap:22px;padding:30px 0;}
          .cgc-hero h1 {font-size:58px!important;}.cgc-hero-copy {max-width:590px;}
          .cgc-hero-copy p {font-size:17px;}
        }
        @media(max-width:600px) {
          [data-testid="stMainBlockContainer"] {padding:5rem 1.2rem 1.2rem;}
          .cgc-logo img {width:94px;}.cgc-header {padding-bottom:18px;}
          .cgc-header-note {font-size:11px;}.cgc-hero h1 {font-size:clamp(41px,10.7vw,58px)!important;}
          .cgc-hero {gap:20px;padding:26px 0;}.cgc-hero-copy p {font-size:16px;}
          [data-baseweb="tab-list"] {gap:20px;}.cgc-empty {padding:22px;min-height:0;}
          .cgc-answer-text {font-size:19px;}.cgc-foot {display:block;}
          .cgc-foot a {margin-top:8px;}h2 {font-size:1.8rem!important;}
        }
        @media(prefers-reduced-motion:reduce) {*,*::before,*::after {animation:none!important;transition:none!important;}}
        </style>""",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    logo = base64.b64encode((ASSETS / "cgc-labs-logo.png").read_bytes()).decode("ascii")
    st.markdown(
        f'<div class="cgc-header"><a class="cgc-logo" href="https://cgclabs.org/" '
        f'target="_blank" rel="noopener noreferrer" aria-label="CGC Labs, home">'
        f'<img src="data:image/png;base64,{logo}" alt="CGC Labs"></a>'
        '<div class="cgc-header-note">Christian Callahan / Engineering study<br>'
        '<a href="https://cgclabs.org/" target="_blank" rel="noopener noreferrer">CGC Labs ↗</a></div></div>'
        '<section class="cgc-hero"><div><div class="cgc-label">Interactive engineering study</div>'
        '<h1>Permission-aware<br><span class="cgc-accent">RAG.</span></h1></div>'
        '<div class="cgc-hero-copy"><p>Choose a synthetic hospital profile. Search records and inspect '
        'the sources, context, and audit chain behind the response.</p>'
        '<small>Python / Streamlit / Synthetic data</small></div></section>',
        unsafe_allow_html=True,
    )


def render_answer(answer: str, labels: Mapping[str, str], status: str) -> None:
    safe_answer = escape(answer)

    def source_reference(match: re.Match[str]) -> str:
        label = labels.get(match.group(1).lower())
        return f'<span class="cgc-citation">{escape(label)}</span>' if label else match.group(0)

    safe_answer = re.sub(r"\[([0-9a-fA-F-]{36})\]", source_reference, safe_answer)
    st.markdown(
        f'<div class="cgc-answer"><div class="cgc-status">{escape(status)}</div>'
        f'<div class="cgc-answer-text">{safe_answer}</div></div>',
        unsafe_allow_html=True,
    )


def render_diagram(filename: str, label: str) -> None:
    image = base64.b64encode((ASSETS / filename).read_bytes()).decode("ascii")
    st.markdown(
        f'<div class="cgc-figure" tabindex="0" role="region" aria-label="{escape(label, quote=True)}">'
        f'<img src="data:image/svg+xml;base64,{image}" alt="{escape(label, quote=True)}"></div>',
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        '<footer class="cgc-foot"><span>Synthetic demo · Local retrieval · No model API</span>'
        '<a href="https://cgclabs.org/" target="_blank" rel="noopener noreferrer">CGC Labs / Engineering study ↗</a></footer>',
        unsafe_allow_html=True,
    )
