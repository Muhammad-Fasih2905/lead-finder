"""All CSS for the dashboard in one place."""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Figtree:wght@400;500;600;700&display=swap');

:root{
  --canvas:#EEF2EF; --card:#FFFFFF; --ink:#0D2B2E; --ink-2:#2F4B4E; --muted:#6A8083; --line:#DCE5E1;
  --teal:#0E7C7B; --teal-d:#0A5E5D; --teal-soft:#DDF0EE; --amber:#FFB400; --amber-soft:#FFF3D1;
  --rose:#B4425A; --rose-soft:#F9E5EA; --sky-soft:#E3EEF7; --good:#168A57;
  --radius:16px;
}
html, body, .stApp, .stMarkdown, .stMarkdown p, button, input, textarea, label, [data-baseweb] { font-family: 'Figtree', system-ui, -apple-system, 'Segoe UI', sans-serif; }
[data-testid="stIconMaterial"], span[class*="material-symbols"], .material-icons { font-family: 'Material Symbols Rounded', 'Material Icons' !important; }
[data-testid="stToolbar"], .stDeployButton, [data-testid="stStatusWidget"] { display:none !important; }
[data-baseweb="tab-highlight"] { background: var(--teal) !important; }
[data-baseweb="tab"][aria-selected="true"], [data-baseweb="tab"][aria-selected="true"] p { color: var(--teal-d) !important; }
[data-testid="stToggle"] [data-baseweb="checkbox"] > div:first-child { background-color: #B9CBC6; }
[data-testid="stToggle"] input:checked + div, [data-testid="stToggle"] [aria-checked="true"] > div:first-child { background-color: var(--teal) !important; }
[data-baseweb="segmented-control"] [aria-checked="true"], [data-testid="stSegmentedControl"] [aria-checked="true"] { background: var(--teal) !important; color:#fff !important; border-color: var(--teal) !important; }
.stApp { background: var(--canvas); color: var(--ink); }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1320px; padding-top: 1.4rem; padding-bottom: 4rem; }
h1,h2,h3,h4 { font-family:'Bricolage Grotesque', 'Figtree', sans-serif; letter-spacing:-0.01em; color:var(--ink); }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] { background: var(--ink); border-right: none; }
section[data-testid="stSidebar"] * { color: #D5E6E3; }
section[data-testid="stSidebar"] a { color: #7FE0D5; }
section[data-testid="stSidebar"] input { color: var(--ink) !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] { border: 1px solid #25494c; border-radius: 12px; background: #11353a; }
section[data-testid="stSidebar"] [data-testid="stExpander"] details, section[data-testid="stSidebar"] [data-testid="stExpander"] summary { background: transparent !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p { color:#fff; font-weight:600; }
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { color:#fff; }
.brand { display:flex; align-items:center; gap:.7rem; margin: .2rem 0 1.1rem; }
.brand-mark { width:38px; height:38px; border-radius:11px; background: var(--amber); display:grid; place-items:center; }
.brand-name { font-family:'Bricolage Grotesque','Figtree',system-ui,sans-serif; font-weight:800; font-size:1.3rem; color:#fff !important; line-height:1.05; }
.brand-sub { font-size:.78rem; color:#8FB3AF !important; }

/* ---------- page header ---------- */
.page-head { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; }
.page-head h1 { margin:0; font-weight:800; font-size:2.1rem; line-height:1.1; }
.page-head p { margin:.35rem 0 0; color:var(--muted); font-size:1rem; max-width:60ch; }

/* ---------- search panel ---------- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div > .search-anchor),
.search-shell { background:var(--card); border:1px solid var(--line); border-radius:var(--radius); }
[data-testid="stTextInput"] input, [data-baseweb="select"] > div, [data-testid="stNumberInput"] input {
  border-radius: 11px !important; border-color: var(--line) !important; background:#F8FAF9 !important; }
[data-testid="stTextInput"] input:focus { border-color: var(--teal) !important; box-shadow: 0 0 0 3px rgba(14,124,123,.18) !important; }
label[data-testid="stWidgetLabel"] p { font-weight:600; color:var(--ink-2); font-size:.86rem; }
.stButton > button, .stDownloadButton > button { border-radius: 11px; font-weight:600; border:1px solid var(--line); transition: transform .08s ease, box-shadow .15s ease; }
.stButton > button:active, .stDownloadButton > button:active { transform: translateY(1px); }
.stButton > button[kind="primary"] { background: var(--teal); border-color: var(--teal); color:#fff; min-height: 2.75rem; }
.stButton > button[kind="primary"]:hover { background: var(--teal-d); border-color: var(--teal-d); }
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible, a:focus-visible { outline: 3px solid var(--amber); outline-offset: 2px; }
.chip-row .stButton > button { border-radius:999px; padding:.15rem .8rem; font-size:.84rem; background:#fff; color:var(--ink-2); min-height:0; }

/* ---------- KPI strip ---------- */
.kpis { display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:.8rem; margin: .4rem 0 1.1rem; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:.85rem 1rem .8rem; }
.kpi-top { display:flex; align-items:baseline; justify-content:space-between; }
.kpi-num { font-family:'Bricolage Grotesque','Figtree',system-ui,sans-serif; font-weight:800; font-size:1.9rem; line-height:1; color:var(--ink); font-variant-numeric: tabular-nums; }
.kpi-pct { font-size:.8rem; color:var(--muted); font-variant-numeric: tabular-nums; }
.kpi-label { font-size:.84rem; color:var(--ink-2); font-weight:600; margin-top:.35rem; }
.kpi-bar { height:5px; background:#E5ECE9; border-radius:99px; margin-top:.55rem; overflow:hidden; }
.kpi-bar > i { display:block; height:100%; background:var(--teal); border-radius:99px; }
.kpi.accent .kpi-bar > i { background: var(--amber); }

/* ---------- lead cards ---------- */
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap:1rem; }
.lead { background:var(--card); border:1px solid var(--line); border-radius:var(--radius); overflow:hidden; display:flex; flex-direction:column;
        box-shadow: 0 1px 0 rgba(13,43,46,.03); }
.lead-top { display:flex; gap:.8rem; align-items:flex-start; padding:1rem 1rem .7rem; }
.lead-title { flex:1; min-width:0; }
.lead-title h3 { margin:0; font-size:1.12rem; font-weight:700; line-height:1.2; overflow-wrap:anywhere; }
.cat { display:inline-block; margin-top:.35rem; font-size:.76rem; font-weight:600; color:var(--teal-d); background:var(--teal-soft); padding:.12rem .55rem; border-radius:99px; }
.ring { --p:0; --c:var(--teal); width:46px; height:46px; border-radius:50%; flex:none; display:grid; place-items:center;
        background: conic-gradient(var(--c) calc(var(--p) * 1%), #E5ECE9 0); position:relative; }
.ring::before { content:""; position:absolute; inset:5px; background:#fff; border-radius:50%; }
.ring b { position:relative; font-family:'Bricolage Grotesque','Figtree',system-ui,sans-serif; font-size:.92rem; font-weight:800; font-variant-numeric: tabular-nums; }
.ring.mid { --c: var(--amber); } .ring.low { --c: #C8D3CF; }

.call { display:flex; align-items:center; gap:.6rem; margin:.1rem 1rem .5rem; padding:.7rem .85rem; border-radius:12px; text-decoration:none !important;
        background: var(--ink); color:#fff !important; font-weight:700; font-size:1.14rem; letter-spacing:.01em; font-variant-numeric: tabular-nums;
        transition: background .15s ease; }
.call:hover { background:#143c40; }
.call svg { flex:none; }
.call .more { margin-left:auto; font-size:.76rem; font-weight:600; color:#9CC3BF; }
.call.none { background: transparent; border:1.5px dashed #C3D2CD; color: var(--muted) !important; font-weight:600; font-size:.95rem; }
.call.none:hover { background:#F4F8F6; }
.call.none a { margin-left:auto; color:var(--teal-d) !important; font-size:.82rem; font-weight:700; text-decoration:underline; }
.alt-phones { margin: -.2rem 1rem .5rem; font-size:.84rem; color:var(--muted); display:flex; gap:.8rem; flex-wrap:wrap; }
.alt-phones a { color:var(--ink-2); font-weight:600; text-decoration:none; border-bottom:1px dotted var(--muted); font-variant-numeric: tabular-nums; }

.rows { padding:.2rem 1rem .8rem; display:flex; flex-direction:column; gap:.5rem; }
.row { display:flex; gap:.6rem; align-items:flex-start; font-size:.93rem; line-height:1.35; min-width:0; }
.row svg { flex:none; margin-top:2px; color:var(--teal); }
.row .val { min-width:0; overflow-wrap:anywhere; }
.row a { color:var(--ink); text-decoration:none; border-bottom:1px solid #BFD3CE; }
.row a:hover { border-bottom-color: var(--teal); color:var(--teal-d); }
.row .sub { color:var(--muted); font-size:.84rem; }
.row.missing { color:var(--muted); }
.row.missing svg { color:#AFC0BC; }
.row.missing a { color:var(--teal-d); border-bottom:none; text-decoration:underline; font-size:.84rem; font-weight:600; margin-left:.3rem; }
.who { font-weight:700; }
.conf { display:inline-block; font-size:.7rem; font-weight:700; padding:.05rem .42rem; border-radius:99px; margin-left:.35rem; vertical-align:1px; }
.conf.High { background:var(--teal-soft); color:var(--teal-d); }
.conf.Medium { background:var(--amber-soft); color:#8A5D00; }
.conf.Low { background:var(--rose-soft); color:var(--rose); }

.lead-foot { margin-top:auto; border-top:1px solid var(--line); padding:.6rem 1rem; display:flex; gap:.4rem; align-items:center; flex-wrap:wrap; background:#FAFCFB; }
.soc { font-size:.78rem; font-weight:600; padding:.12rem .55rem; border-radius:99px; background:var(--sky-soft); color:#235079; text-decoration:none !important; }
.src { margin-left:auto; font-size:.76rem; color:var(--muted); }
.src a { color:var(--muted); }

/* ---------- empty state ---------- */
.empty { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:2.2rem 2rem; display:grid; grid-template-columns: 1.1fr 1fr; gap:2rem; align-items:center; margin-top:.4rem; }
.empty h2 { margin:0 0 .5rem; font-weight:800; font-size:1.7rem; }
.empty p { color:var(--ink-2); margin:0 0 .5rem; max-width:52ch; line-height:1.5; }
.sample { background: var(--canvas); border-radius:16px; padding:1rem; transform: rotate(1.2deg); border:1px solid var(--line); }
.sample .lead { box-shadow: 0 10px 30px rgba(13,43,46,.10); }

/* ---------- misc ---------- */
.notice { background:var(--amber-soft); border:1px solid #F3DC9A; color:#6B4A00; padding:.65rem .9rem; border-radius:12px; font-size:.9rem; margin:.4rem 0 .8rem; }
.foot { color:var(--muted); font-size:.8rem; margin-top:2rem; }
[data-baseweb="tab-list"] { gap:.4rem; }
[data-baseweb="tab"] { font-weight:600; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }

@media (max-width: 1000px) { .kpis { grid-template-columns: repeat(2, minmax(0,1fr)); } .empty { grid-template-columns: 1fr; } .sample{display:none} }
@media (max-width: 560px) { .grid { grid-template-columns: 1fr; } .page-head h1 { font-size:1.7rem; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""
