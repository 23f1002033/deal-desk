"""
Deal Desk — AI Deal Operating System (demo frontend).

A three-column enterprise console for the Band of Agents Hackathon submission:

  · Left   — the customer RFP
  · Center — the live multi-agent workflow (pipeline, agent cards, activity feed)
  · Right  — the generated proposal, quality score, risk analysis, exports

It runs the same agent prompts (prompts.py) the Band agents use, live, so judges
can watch the Coordinator recruit specialists, the Reviewer red-team each section,
a >20% discount escalate to a human, and the final proposal get scored.

Config (Streamlit secrets / env — never the UI):
  AIML_API_KEY (required) · AIML_BASE_URL · MODEL · APP_PASSCODE (optional gate)

Run locally:  uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime

import markdown as md
import streamlit as st
from dotenv import load_dotenv

from frontend.orchestrator import DealDesk, Event, run_deal_desk

load_dotenv()
st.set_page_config(page_title="Deal Desk — AI Deal OS", page_icon="🤝", layout="wide")

# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
ROLE = {
    "pricing": {"name": "Pricing Specialist", "emoji": "💰", "color": "#059669", "role": "Pricing"},
    "technical": {"name": "Technical Specialist", "emoji": "🛠️", "color": "#0284c7", "role": "Solution"},
    "legal": {"name": "Legal Specialist", "emoji": "⚖️", "color": "#9333ea", "role": "Compliance"},
}
SYS_AGENTS = {
    "coordinator": {"name": "Coordinator", "emoji": "🧭", "color": "#6366f1", "role": "Orchestration"},
    "reviewer": {"name": "Reviewer", "emoji": "🔎", "color": "#d97706", "role": "Quality gate"},
}
AGENT_ORDER = ["coordinator", "pricing", "technical", "legal", "reviewer"]
ACTOR_COLOR = {
    "Coordinator": "#6366f1", "Pricing Specialist": "#059669", "Technical Specialist": "#0284c7",
    "Legal Specialist": "#9333ea", "Reviewer": "#d97706", "Human": "#e11d48",
}
STATUS = {
    "idle": ("Idle", "#94a3b8", False),
    "recruited": ("Recruited", "#6366f1", False),
    "drafting": ("Drafting", "#0284c7", True),
    "review": ("In Review", "#d97706", True),
    "reviewing": ("Reviewing", "#d97706", True),
    "orchestrating": ("Orchestrating", "#6366f1", True),
    "approved": ("Approved", "#059669", False),
    "flagged": ("Flagged", "#d97706", False),
    "done": ("Complete", "#059669", False),
}
STATUS_CONF = {"recruited": 15, "drafting": 45, "review": 70, "approved": 92, "flagged": 72}
PHASES = [("triage", "Triage"), ("recruit", "Recruit"), ("draft", "Draft"),
          ("review", "Review"), ("approve", "Approve"), ("done", "Done")]
PHASE_IDX = {k: i for i, (k, _) in enumerate(PHASES)}
SEV_COLOR = {"low": "#059669", "medium": "#d97706", "high": "#e11d48"}

esc = html.escape

# --------------------------------------------------------------------------- #
# Design system
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
      :root { --bg:#f6f7fb; --panel:#ffffff; --line:#e9ebf2; --line-2:#eef0f6;
              --txt:#11131c; --txt-2:#3b4256; --muted:#737a90; --faint:#9aa0b3; --accent:#6366f1;
              --r:16px; --sh:0 1px 2px #1c20300a, 0 8px 24px -16px #2a346b40; }
      .stApp { background:
          radial-gradient(1200px 640px at 6% -16%, #eaecff 0%, transparent 50%),
          radial-gradient(1000px 620px at 104% -10%, #e6f2fb 0%, transparent 46%), var(--bg); }
      header[data-testid="stHeader"] { background:transparent; }
      #MainMenu, footer { visibility:hidden; }
      .block-container { padding-top:1.5rem; padding-bottom:2.4rem; max-width:1500px; }
      html, body, [class*="css"] { font-family:'Inter','Segoe UI',system-ui,sans-serif; color:var(--txt);
              -webkit-font-smoothing:antialiased; }
      h1,h2,h3,h4 { color:var(--txt); letter-spacing:-.018em; }

      @keyframes fadeUp { from{opacity:0; transform:translateY(6px)} to{opacity:1; transform:none} }
      @keyframes pulse { 0%{box-shadow:0 0 0 0 var(--pc)} 70%{box-shadow:0 0 0 6px transparent} 100%{box-shadow:0 0 0 0 transparent} }
      @keyframes breathe { 0%,100%{opacity:.45} 50%{opacity:.9} }

      .glass { background:rgba(255,255,255,.72); backdrop-filter:blur(18px) saturate(160%);
               -webkit-backdrop-filter:blur(18px) saturate(160%);
               border:1px solid rgba(255,255,255,.85); border-radius:var(--r);
               box-shadow:var(--sh), inset 0 1px 0 #ffffffd9; }
      .card-s { background:#fff; border:1px solid var(--line); border-radius:14px; box-shadow:var(--sh); }

      /* top bar */
      .topbar { display:flex; align-items:center; justify-content:space-between; padding:.8rem 1.25rem; margin-bottom:1.15rem; }
      .brand { display:flex; align-items:center; gap:.7rem; }
      .brand .logo { font-size:1.55rem; filter:drop-shadow(0 3px 7px #6366f155); }
      .brand .nm { font-size:1.16rem; font-weight:800; letter-spacing:-.02em;
                   background:linear-gradient(90deg,#4f46e5,#7c3aed); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
      .brand .tag { font-size:.66rem; font-weight:800; letter-spacing:.08em; color:#8089a3; border:1px solid var(--line);
                    padding:.16rem .5rem; border-radius:7px; background:#fbfbfe; }
      .pill { display:inline-flex; align-items:center; gap:.45rem; font-size:.74rem; font-weight:700; padding:.34rem .72rem; border-radius:999px; }
      .pill.ok { background:#ecfaf2; color:#0a8a4d; border:1px solid #bfe9cf; }
      .pill.off { background:#fdeef0; color:#c0334a; border:1px solid #f4c4ce; }
      .dotled { width:7px; height:7px; border-radius:50%; background:currentColor; animation:breathe 2.2s ease infinite; }

      /* KPI tiles */
      .tiles { display:grid; grid-template-columns:repeat(5,1fr); gap:.75rem; margin-bottom:1.15rem; }
      .tile { padding:1.05rem 1.1rem; animation:fadeUp .45s ease both; min-height:104px; }
      .tile .k { font-size:.67rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--faint); }
      .tile .v { font-size:1.6rem; font-weight:800; margin-top:.35rem; letter-spacing:-.03em; line-height:1.05; color:var(--txt); }
      .tile .v.ph { color:#c2c8d6; font-weight:700; }
      .tile .s { font-size:.72rem; color:var(--muted); margin-top:.28rem; }
      .tile .s.calc { color:var(--accent); animation:breathe 1.6s ease infinite; font-weight:600; }
      .tilewrap { display:flex; align-items:center; justify-content:space-between; gap:.6rem; }
      .ring { position:relative; width:58px; height:58px; border-radius:50%; display:grid; place-items:center; flex:none; }
      .ring .in { width:44px; height:44px; border-radius:50%; background:#fff; display:grid; place-items:center; font-weight:800; font-size:.82rem; }
      .sevdots { display:flex; gap:.28rem; margin-top:.55rem; }
      .sevdots i { width:8px; height:8px; border-radius:50%; display:inline-block; }

      /* section labels */
      .lab { font-size:.7rem; font-weight:800; letter-spacing:.11em; text-transform:uppercase; color:var(--faint);
             margin:.1rem 0 .7rem; display:flex; align-items:center; gap:.5rem; }
      .lab .num { width:1.15rem; height:1.15rem; border-radius:6px; display:grid; place-items:center; font-size:.66rem;
                  color:#fff; background:linear-gradient(135deg,#6366f1,#8b5cf6); }
      .panel { padding:1.05rem 1.1rem; animation:fadeUp .4s ease both; }

      /* pipeline */
      .pipe { display:flex; gap:.3rem; align-items:center; flex-wrap:wrap; margin-bottom:1rem; }
      .step { font-size:.69rem; font-weight:700; padding:.26rem .66rem; border-radius:8px; border:1px solid var(--line); color:var(--faint); background:#fff; }
      .step.done { background:#ecfaf2; border-color:#bfe9cf; color:#0a8a4d; }
      .step.cur { background:#eef0ff; border-color:var(--accent); color:#4338ca; box-shadow:0 0 0 3px #6366f11f; }
      .arr { color:#cdd2df; font-size:.6rem; }

      /* agent cards */
      .agrid { display:grid; grid-template-columns:1fr 1fr; gap:.7rem; }
      .ag { padding:.85rem .9rem; border-radius:14px; background:#fff; border:1px solid var(--line);
            animation:fadeUp .4s ease both; box-shadow:var(--sh); transition:border-color .2s, box-shadow .2s; }
      .ag.is-live { border-color:#c9ccf7; box-shadow:0 1px 2px #1c20300a, 0 10px 26px -16px #6366f180; }
      .ag .h { display:flex; align-items:center; gap:.55rem; }
      .ag .av { width:32px; height:32px; border-radius:9px; display:grid; place-items:center; font-size:1.02rem; color:#fff; flex:none;
                box-shadow:0 4px 10px -5px currentColor; }
      .ag .nm { font-size:.85rem; font-weight:700; line-height:1.1; }
      .ag .rl { font-size:.67rem; color:var(--muted); }
      .ag .st { margin-left:auto; font-size:.63rem; font-weight:800; letter-spacing:.02em; padding:.16rem .5rem; border-radius:999px;
                display:flex; align-items:center; gap:.34rem; }
      .ag .st .d { width:6px; height:6px; border-radius:50%; background:currentColor; }
      .ag .st.live .d { animation:pulse 1.5s infinite; }
      .bar { height:5px; border-radius:99px; background:#eef0f6; margin-top:.75rem; overflow:hidden; }
      .bar .f { height:100%; border-radius:99px; transition:width .6s cubic-bezier(.4,0,.2,1); }
      .ag .meta { display:flex; justify-content:space-between; margin-top:.5rem; font-size:.67rem; color:var(--muted); }
      .ag .fnd { font-weight:700; color:var(--txt-2); }

      /* activity console */
      .feed { padding:0; max-height:316px; overflow:auto; }
      .feed-h { display:flex; align-items:center; gap:.5rem; padding:.55rem .8rem; border-bottom:1px solid var(--line-2);
                font-size:.66rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
                position:sticky; top:0; background:rgba(255,255,255,.86); backdrop-filter:blur(6px); }
      .feed-h .live { margin-left:auto; display:flex; align-items:center; gap:.34rem; color:#0a8a4d; }
      .feed-h .live i { width:6px; height:6px; border-radius:50%; background:#16a34a; animation:breathe 1.4s infinite; }
      .ln { display:grid; grid-template-columns:auto auto 1fr; gap:.6rem; align-items:baseline; padding:.46rem .8rem;
            border-bottom:1px solid var(--line-2); animation:fadeUp .3s ease both; }
      .ln:last-child { border-bottom:none; }
      .ln:hover { background:#fafbff; }
      .ts { font-size:.66rem; font-variant-numeric:tabular-nums; color:#aab0c2;
            font-family:'SFMono-Regular',ui-monospace,Menlo,monospace; }
      .bdg { color:#fff; font-size:.6rem; font-weight:800; letter-spacing:.02em; padding:.1rem .44rem; border-radius:6px; white-space:nowrap; }
      .tx { font-size:.78rem; color:var(--txt-2); line-height:1.35; }

      /* skipped */
      .skip { margin-top:.8rem; font-size:.71rem; color:var(--muted); padding:.5rem .7rem; background:#fafbff;
              border:1px solid var(--line-2); border-radius:10px; }
      .skip b { color:var(--txt-2); font-weight:700; }

      /* risks */
      .risk { padding:.7rem .8rem; border-radius:12px; background:#fff; border:1px solid var(--line);
              border-left:3px solid #d97706; margin-bottom:.55rem; animation:fadeUp .4s ease both; box-shadow:var(--sh); }
      .risk .t { font-size:.81rem; font-weight:700; display:flex; justify-content:space-between; gap:.5rem; align-items:center; }
      .risk .sev { font-size:.59rem; font-weight:800; letter-spacing:.04em; padding:.1rem .42rem; border-radius:999px; color:#fff; text-transform:uppercase; }
      .risk .m { font-size:.74rem; color:var(--muted); margin-top:.3rem; line-height:1.4; }

      /* empty + loading */
      .empty { text-align:center; color:var(--faint); padding:2.4rem 1.2rem; font-size:.85rem; line-height:1.5; }
      .empty .ic { font-size:1.7rem; opacity:.45; display:block; margin-bottom:.5rem; }
      .gen { display:flex; align-items:center; gap:.7rem; padding:1.2rem 1.2rem; color:var(--muted); font-size:.84rem; font-weight:600; }
      .gen .sp { width:16px; height:16px; border-radius:50%; border:2.5px solid #e3e6f2; border-top-color:var(--accent);
                 animation:spin .8s linear infinite; }
      @keyframes spin { to{transform:rotate(360deg)} }

      /* proposal document */
      .doc { max-height:620px; overflow:auto; padding:1.6rem 1.7rem; }
      .doc h1 { font-size:1.35rem; font-weight:800; letter-spacing:-.02em; margin:0 0 .2rem; }
      .doc h2 { font-size:1rem; font-weight:800; color:#1b2030; margin:1.4rem 0 .55rem; padding-bottom:.4rem;
                border-bottom:1px solid var(--line); letter-spacing:.01em; }
      .doc h2:first-of-type { margin-top:1rem; }
      .doc h3 { font-size:.86rem; font-weight:800; color:var(--txt-2); text-transform:uppercase; letter-spacing:.05em; margin:1rem 0 .4rem; }
      .doc p, .doc li { font-size:.83rem; line-height:1.62; color:var(--txt-2); }
      .doc strong { color:var(--txt); font-weight:700; }
      .doc ul { margin:.3rem 0 .6rem; padding-left:1.1rem; }
      .doc li { margin:.18rem 0; }
      .doc hr { border:none; border-top:1px solid var(--line); margin:1rem 0; }
      .doc table { width:100%; border-collapse:collapse; margin:.6rem 0 1rem; font-size:.78rem; }
      .doc th { text-align:left; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.04em;
                font-size:.68rem; padding:.5rem .6rem; background:#fafbff; border-bottom:1px solid var(--line); }
      .doc td { padding:.5rem .6rem; border-bottom:1px solid var(--line-2); color:var(--txt-2); vertical-align:top; }
      .doc tr:hover td { background:#fcfcff; }
      .doc-top { display:flex; align-items:center; gap:.55rem; padding:.7rem 1.7rem; border-bottom:1px solid var(--line);
                 font-size:.66rem; font-weight:800; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); }
      .doc-top .seal { color:#0a8a4d; }

      /* inputs / buttons */
      section[data-testid="stSidebar"] { background:#fbfbfe; border-right:1px solid var(--line); }
      .stTextArea textarea { background:#fff !important; color:var(--txt) !important; border:1px solid var(--line) !important;
              border-radius:12px !important; font-size:.82rem !important; line-height:1.5 !important; box-shadow:var(--sh); }
      .stTextArea textarea:focus { border-color:var(--accent) !important; box-shadow:0 0 0 3px #6366f11f !important; }
      .stTextInput input { background:#fff !important; color:var(--txt) !important; border:1px solid var(--line) !important; border-radius:11px !important; }
      div[data-baseweb="select"] > div { background:#fff !important; border:1px solid var(--line) !important; border-radius:11px !important; box-shadow:var(--sh); }
      .stButton > button, .stDownloadButton > button { border-radius:11px; font-weight:700; border:1px solid var(--line); transition:.15s; }
      .stButton > button:hover, .stDownloadButton > button:hover { border-color:#c9ccf7; }
      .stButton > button[kind="primary"] { background:linear-gradient(135deg,#6366f1,#7c5cf6); color:#fff; border:none;
              padding:.62rem 1rem; font-size:.92rem; letter-spacing:.01em; box-shadow:0 10px 24px -10px #6366f1cc; }
      .stButton > button[kind="primary"]:hover { filter:brightness(1.05); transform:translateY(-1px); box-shadow:0 14px 30px -10px #6366f1cc; }
      .stDownloadButton > button { font-size:.78rem; padding:.45rem .5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


API_KEY = _secret("AIML_API_KEY") or os.getenv("AIML_API_KEY", "")
BASE_URL = _secret("AIML_BASE_URL") or os.getenv("AIML_BASE_URL") or "https://api.aimlapi.com/v1"
MODEL = _secret("MODEL") or os.getenv("MODEL") or "gpt-4o"
PASSCODE = _secret("APP_PASSCODE") or os.getenv("APP_PASSCODE", "")


def _load(path: str) -> str:
    try:
        with open(os.path.join(os.path.dirname(__file__), path), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


SAMPLES = {
    "CRM Migration (full team)": _load("sample_rfp.md"),
    "Startup discount escalation (>20% → human approval)": _load("sample_rfp_escalation.md"),
    "Blank — paste your own": "",
}

# --------------------------------------------------------------------------- #
# Top bar
# --------------------------------------------------------------------------- #
conn = ("<span class='pill ok'><span class='dotled'></span>Connected · " + esc(MODEL) + "</span>") if API_KEY \
    else "<span class='pill off'>Not configured</span>"
st.markdown(
    "<div class='topbar glass'><div class='brand'><span class='logo'>🤝</span>"
    "<span class='nm'>Deal Desk</span><span class='tag'>AI DEAL OS</span></div>"
    f"<div>{conn}</div></div>",
    unsafe_allow_html=True,
)

# Optional access gate (protects API credits on a public URL).
if PASSCODE and not st.session_state.get("authed"):
    st.markdown("<div class='lab'>🔒 Secure access</div>", unsafe_allow_html=True)
    code = st.text_input("Access code", type="password", label_visibility="collapsed", placeholder="Enter access code")
    if st.button("Unlock workspace", type="primary"):
        if code == PASSCODE:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Incorrect access code.")
    st.stop()


# --------------------------------------------------------------------------- #
# Render helpers (all dynamic text is HTML-escaped)
# --------------------------------------------------------------------------- #
def ring(pct: int, color: str) -> str:
    return (f"<div class='ring' style='background:conic-gradient({color} {pct}%, #e8eaf2 0)'>"
            f"<div class='in' style='color:{color}'>{pct}%</div></div>")


KPI_LABELS = [
    ("Deal Value", "Total contract value"),
    ("Win Probability", "Likelihood to close"),
    ("Proposal Quality", "Completeness score"),
    ("Open Risks", "Flagged for review"),
    ("Timeline", "Estimated delivery"),
]


def render_dashboard(m: dict | None, loading: bool = False) -> str:
    if not m:
        sub_cls, sub = ("s calc", "Calculating…") if loading else ("s", "Awaiting analysis")
        val = "···" if loading else "—"
        tiles = "".join(
            f"<div class='tile glass'><div class='k'>{esc(k)}</div>"
            f"<div class='v ph'>{val}</div><div class='{sub_cls}'>{esc(sub)}</div></div>"
            for k, _ in KPI_LABELS
        )
        return f"<div class='tiles'>{tiles}</div>"
    risks = m.get("risks", [])
    counts = {"high": 0, "medium": 0, "low": 0}
    for r in risks:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    dots = "".join(f"<i style='background:{SEV_COLOR[s]}'></i>" * counts[s] for s in ("high", "medium", "low")) or \
        "<i style='background:#cbd2e0'></i>"
    wp, qs = m["win_probability"], m["quality_score"]
    wc = "#059669" if wp >= 65 else "#d97706" if wp >= 40 else "#e11d48"
    qc = "#059669" if qs >= 75 else "#d97706" if qs >= 50 else "#e11d48"
    return (
        "<div class='tiles'>"
        f"<div class='tile glass'><div class='k'>Deal Value</div><div class='v'>{esc(m['deal_value'])}</div>"
        "<div class='s'>Total contract value</div></div>"
        f"<div class='tile glass'><div class='k'>Win Probability</div>"
        f"<div class='tilewrap'><div class='v' style='color:{wc}'>{wp}%</div>{ring(wp, wc)}</div></div>"
        f"<div class='tile glass'><div class='k'>Proposal Quality</div>"
        f"<div class='tilewrap'><div class='v' style='color:{qc}'>{qs}</div>{ring(qs, qc)}</div></div>"
        f"<div class='tile glass'><div class='k'>Open Risks</div><div class='v'>{len(risks)}</div>"
        f"<div class='sevdots'>{dots}</div></div>"
        f"<div class='tile glass'><div class='k'>Timeline</div><div class='v'>{esc(m['timeline'])}</div>"
        "<div class='s'>Estimated delivery</div></div>"
        "</div>"
    )


def render_pipeline(idx: int) -> str:
    parts = []
    for i, (_, label) in enumerate(PHASES):
        cls = "done" if i < idx else ("cur" if i == idx else "")
        parts.append(f"<span class='step {cls}'>{label}</span>")
        if i < len(PHASES) - 1:
            parts.append("<span class='arr'>▸</span>")
    return f"<div class='pipe'>{''.join(parts)}</div>"


def _agent_meta(aid: str) -> dict:
    return SYS_AGENTS[aid] if aid in SYS_AGENTS else ROLE[aid]


def render_agents(agents: dict) -> str:
    cards = []
    for aid in AGENT_ORDER:
        a = agents.get(aid)
        if not a:
            continue
        meta = _agent_meta(aid)
        label, scol, live = STATUS[a["status"]]
        conf = a.get("confidence", 0)
        is_spec = aid in ROLE
        bar = (f"<div class='bar'><div class='f' style='width:{conf}%;background:{meta['color']}'></div></div>"
               f"<div class='meta'><span>Confidence {conf}%</span>"
               f"<span class='fnd'>{a.get('findings', 0)} findings</span></div>") if is_spec else (
               f"<div class='meta' style='margin-top:.55rem'><span>{esc(a.get('note', meta['role']))}</span></div>")
        cards.append(
            f"<div class='ag {'is-live' if live else ''}' style='--pc:{scol}55'><div class='h'>"
            f"<div class='av' style='background:{meta['color']};color:{meta['color']}'>{meta['emoji']}</div>"
            f"<div><div class='nm'>{esc(meta['name'])}</div><div class='rl'>{esc(meta['role'])}</div></div>"
            f"<div class='st {'live' if live else ''}' style='background:{scol}1a;color:{scol}'>"
            f"<span class='d'></span>{label}</div></div>{bar}</div>"
        )
    return f"<div class='agrid'>{''.join(cards)}</div>"


def render_feed(activity: list, running: bool = False) -> str:
    live = "<span class='live'><i></i>LIVE</span>" if running else ""
    header = f"<div class='feed-h'>⬡ Operations Log{live}</div>"
    if not activity:
        body = "<div class='empty'><span class='ic'>📡</span>Agent activity will stream here in real time.</div>"
    else:
        rows = []
        for item in activity[-14:]:
            actor, text, ts = item if len(item) == 3 else (item[0], item[1], "")
            color = ACTOR_COLOR.get(actor, "#8b8fa3")
            rows.append(
                f"<div class='ln'><span class='ts'>{esc(ts)}</span>"
                f"<span class='bdg' style='background:{color}'>{esc(actor)}</span>"
                f"<span class='tx'>{esc(text)}</span></div>"
            )
        body = "".join(rows)
    return f"<div class='feed glass'>{header}{body}</div>"


def render_skipped(skipped: dict) -> str:
    if not skipped:
        return ""
    items = ", ".join(f"<b>{ROLE[r]['emoji']} {esc(ROLE[r]['name'])}</b> ({esc(reason)})" for r, reason in skipped.items())
    return f"<div class='skip'>Not recruited — {items}</div>"


def render_risks(risks: list) -> str:
    if not risks:
        return "<div class='empty'>No material risks flagged.</div>"
    out = []
    for r in risks:
        c = SEV_COLOR[r["severity"]]
        out.append(
            f"<div class='risk' style='border-left-color:{c}'><div class='t'>{esc(r['title'])}"
            f"<span class='sev' style='background:{c}'>{esc(r['severity'])}</span></div>"
            f"<div class='m'>{esc(r['mitigation'])}</div></div>"
        )
    return "".join(out)


def _findings(text: str) -> int:
    return len(re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", text or ""))


def render_proposal(final: str) -> str:
    # Escape first so any HTML in the (LLM/RFP-derived) text is inert, then format
    # the markdown — markdown syntax chars survive html.escape, raw tags do not.
    body = md.markdown(esc(final), extensions=["tables", "sane_lists"])
    return (
        "<div class='glass'><div class='doc-top'><span class='seal'>●</span>"
        "Confidential · Prepared by AI Deal Desk</div>"
        f"<div class='doc'>{body}</div></div>"
    )


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
dash_ph = st.empty()
left, center, right = st.columns([1.0, 1.55, 1.2], gap="large")

with left:
    st.markdown("<div class='lab'><span class='num'>1</span>Customer RFP</div>", unsafe_allow_html=True)
    choice = st.selectbox("Sample", list(SAMPLES.keys()), label_visibility="collapsed")
    rfp = st.text_area("RFP", value=SAMPLES[choice], height=430, key=f"rfp_{choice}", label_visibility="collapsed")
    run = st.button("▶  Run Deal Desk", type="primary", use_container_width=True)
    left_ctx = st.empty()

with center:
    st.markdown("<div class='lab'><span class='num'>2</span>Live Workflow</div>", unsafe_allow_html=True)
    pipe_ph = st.empty()
    cards_ph = st.empty()
    skip_ph = st.empty()
    st.markdown("<div class='lab' style='margin-top:1.1rem'>📡 Activity Feed</div>", unsafe_allow_html=True)
    feed_ph = st.empty()

with right:
    st.markdown("<div class='lab'><span class='num'>3</span>Proposal Output</div>", unsafe_allow_html=True)
    out_ph = st.empty()
    right_box = st.container()

# Idle state
if not st.session_state.get("go"):
    dash_ph.markdown(render_dashboard(None), unsafe_allow_html=True)
    pipe_ph.markdown(render_pipeline(-1), unsafe_allow_html=True)
    base_agents = {k: {"status": "idle", "confidence": 0, "findings": 0} for k in ("coordinator", "reviewer")}
    cards_ph.markdown(render_agents(base_agents), unsafe_allow_html=True)
    feed_ph.markdown(render_feed([]), unsafe_allow_html=True)
    out_ph.markdown(
        "<div class='glass empty'><span class='ic'>📑</span>"
        "Your boardroom-ready proposal, quality score, and risk analysis<br>will appear here once the team runs.</div>",
        unsafe_allow_html=True,
    )

# Trigger
if run:
    if not API_KEY:
        st.error("No AI/ML API key configured. Set AIML_API_KEY as a secret, or paste one in the sidebar (local).")
    elif not rfp.strip():
        st.error("Paste an RFP (or pick a sample) first.")
    else:
        for k in ("prior", "approvals"):
            st.session_state.pop(k, None)
        st.session_state.update(go=True, rfp=rfp)
        st.rerun()

# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
if st.session_state.get("go"):
    rfp = st.session_state["rfp"]
    approvals = st.session_state.get("approvals", {})
    prior = st.session_state.get("prior")

    agents = {
        "coordinator": {"status": "orchestrating", "confidence": 0, "findings": 0, "note": "Reading RFP…"},
        "reviewer": {"status": "idle", "confidence": 0, "findings": 0, "note": "Quality gate"},
    }
    state = {"skipped": {}, "activity": [], "phase": 0}

    if prior:  # resuming after human approval — repopulate the board
        for r in prior["decision"].recruit:
            agents[r] = {**{"status": "approved", "findings": 0, "rounds": 1}, "confidence": 92}
        for s in prior["decision"].skip:
            state["skipped"][s["role"]] = s.get("reason", "")
        agents["coordinator"]["status"] = "orchestrating"
        state["phase"] = PHASE_IDX["approve"]

    def _bump(p): state["phase"] = max(state["phase"], PHASE_IDX[p])

    def _paint():
        pipe_ph.markdown(render_pipeline(state["phase"]), unsafe_allow_html=True)
        cards_ph.markdown(render_agents(agents), unsafe_allow_html=True)
        skip_ph.markdown(render_skipped(state["skipped"]), unsafe_allow_html=True)
        feed_ph.markdown(render_feed(state["activity"], running=True), unsafe_allow_html=True)

    def emit(ev: Event):
        role = ev.meta.get("role")
        rev = agents["reviewer"]
        if ev.kind == "status" and ev.title.startswith("Customer:"):
            left_ctx.markdown(f"<div class='panel glass' style='margin-top:.7rem'><div class='lab'>Deal context</div>"
                              f"<div class='tx'>{esc(ev.title.replace('**',''))}</div></div>", unsafe_allow_html=True)
        if ev.kind == "recruit" and role:
            agents[role] = {"status": "recruited", "confidence": STATUS_CONF["recruited"], "findings": 0, "rounds": 0}
            _bump("recruit")
        elif ev.kind == "skip" and role:
            state["skipped"][role] = ev.body; _bump("recruit")
        elif ev.kind == "status" and role and "Drafting" in ev.title:
            agents[role]["status"] = "drafting"; agents[role]["confidence"] = STATUS_CONF["drafting"]; _bump("draft")
        elif ev.kind == "section" and role:
            agents[role]["status"] = "review"; agents[role]["confidence"] = STATUS_CONF["review"]
            rev["status"] = "reviewing"; _bump("review")
        elif ev.kind == "status" and role:  # reviewer red-teaming
            rev["status"] = "reviewing"; _bump("review")
        elif ev.kind == "review" and role:
            f = _findings(ev.body); agents[role]["findings"] += f; rev["findings"] += f
            agents[role]["rounds"] = agents[role].get("rounds", 0) + 1
            if ev.meta.get("approved"):
                agents[role]["status"] = "approved"
                agents[role]["confidence"] = 96 if agents[role]["rounds"] == 1 else 88
            else:
                agents[role]["status"] = "drafting"; agents[role]["confidence"] = STATUS_CONF["drafting"]
            rev["status"] = "idle"; rev["note"] = f"{rev['findings']} findings raised"; _bump("review")
        elif ev.kind == "rule" and role and "max review" in ev.title:
            agents[role]["status"] = "flagged"; agents[role]["confidence"] = STATUS_CONF["flagged"]
        elif ev.kind == "rule" and ("APPROVAL" in ev.title or "budget" in ev.title.lower()):
            _bump("approve")
        elif ev.kind == "status" and "Reading the RFP" in ev.title:
            _bump("triage")
        elif ev.kind in ("final", "done"):
            agents["coordinator"]["status"] = "done"; agents["coordinator"]["note"] = "Proposal assembled"
            rev["status"] = "idle"; _bump("done")

        if ev.kind != "metrics":
            text = {
                "recruit": ev.title, "skip": ev.title, "rule": ev.title,
                "review": ("APPROVED ✓" if ev.meta.get("approved") else "Sent back for revision"),
                "section": f"{ev.actor} section drafted",
                "final": "Final proposal assembled", "done": ev.title,
            }.get(ev.kind, ev.title)
            agents["coordinator"]["note"] = "Orchestrating…" if agents["coordinator"]["status"] == "orchestrating" else agents["coordinator"].get("note", "")
            state["activity"].append((ev.actor, text.replace("**", ""), datetime.now().strftime("%H:%M:%S")))
        else:
            dash_ph.markdown(render_dashboard(ev.meta), unsafe_allow_html=True)
        _paint()

    # Calculating states while the team works (no blank skeletons).
    dash_ph.markdown(render_dashboard(None, loading=True), unsafe_allow_html=True)
    out_ph.markdown("<div class='glass'><div class='gen'><span class='sp'></span>"
                    "Specialists are drafting — the proposal is assembling…</div></div>",
                    unsafe_allow_html=True)
    _paint()

    try:
        desk = DealDesk(api_key=API_KEY, base_url=BASE_URL, model=MODEL)
        with st.spinner("Agents are coordinating…"):
            result = run_deal_desk(desk, rfp, emit, approvals=approvals, prior=prior)
    except Exception as exc:
        out_ph.empty()
        st.error("The run failed while calling the model. Check the API key / endpoint and try again.")
        st.caption(f"Details: {type(exc).__name__}")
        result = None

    # ---- human approval ---------------------------------------------------- #
    if result and result.get("pending_approval"):
        pa = result["pending_approval"]
        st.session_state["prior"] = {"decision": result["decision"], "sections": result["sections"]}
        out_ph.empty()
        with right_box:
            st.markdown("<div class='lab' style='color:#c0334a'>🔴 Approval required</div>", unsafe_allow_html=True)
            st.warning(f"Pricing proposed a **{pa['discount']:g}% discount** — above the 20% policy threshold. "
                       "The Coordinator paused and pulled you in.")
            a, b = st.columns(2)
            if a.button("✅ Approve", type="primary", use_container_width=True):
                st.session_state["approvals"] = {"discount": True}; st.rerun()
            if b.button("❌ Reject", use_container_width=True):
                st.session_state["approvals"] = {"discount": False}; st.rerun()

    # ---- final proposal ---------------------------------------------------- #
    elif result and result.get("final"):
        final = result["final"]
        metrics = result.get("metrics", {})
        dash_ph.markdown(render_dashboard(metrics), unsafe_allow_html=True)
        out_ph.markdown(render_proposal(final), unsafe_allow_html=True)
        with right_box:
            if metrics.get("risks") is not None:
                st.markdown("<div class='lab' style='margin-top:1.1rem'>⚠️ Risk Analysis</div>", unsafe_allow_html=True)
                st.markdown(render_risks(metrics["risks"]), unsafe_allow_html=True)
            st.markdown("<div class='lab' style='margin-top:1.1rem'>⬇️ Export Proposal</div>", unsafe_allow_html=True)
            e1, e2, e3 = st.columns(3)
            e1.download_button("Markdown", final, "proposal.md", "text/markdown", use_container_width=True)
            try:
                from frontend.exporters import to_docx, to_pdf
                e2.download_button("DOCX", to_docx(final), "proposal.docx",
                                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   use_container_width=True)
                e3.download_button("PDF", to_pdf(final), "proposal.pdf", "application/pdf", use_container_width=True)
            except Exception:
                e2.caption("DOCX/PDF unavailable")
        st.session_state["go"] = False

    elif result and result.get("rejected"):
        out_ph.empty()
        with right_box:
            st.error("The human rejected the discount — proposal halted.")
        st.session_state["go"] = False
