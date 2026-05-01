import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import plotly.graph_objects as go

# CONFIG
MANAGERS = {
    1630460: {"name": "Zee", "team": "Sesko n Destroy", "yours": True},
    533668:  {"name": "Sam", "team": "Fergie Time United", "yours": False},
    7617214: {"name": "Joey", "team": "BAKHAAT", "yours": False}
}

OUTPUT_FILE = "index.html"


# ====================== DATA FETCHING ======================
def get_bootstrap_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"

    try:
        data = requests.get(url, timeout=10).json()
        events = data.get("events", [])
        current_gw = next((e["id"] for e in events if e.get("is_current")), None)

        if current_gw is None:
            processed = [
                e["id"] for e in events
                if e.get("data_checked") or e.get("finished")
            ]
            current_gw = max(processed) if processed else events[-1]["id"]

        players = {p["id"]: p["web_name"] for p in data.get("elements", [])}

        print(f"Debug: GW {current_gw} detected")
        return current_gw, players

    except Exception as e:
        raise Exception(f"Bootstrap failed: {e}")


def get_manager_summary(entry_id):
    try:
        data = requests.get(
            f"https://fantasy.premierleague.com/api/entry/{entry_id}/",
            timeout=8
        ).json()

        return (
            data.get("summary_overall_points", 0),
            data.get("summary_overall_rank", "N/A")
        )
    except Exception:
        return 0, "N/A"


def get_picks(entry_id, gw):
    try:
        data = requests.get(
            f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/",
            timeout=8
        ).json()

        points = data.get("entry_history", {}).get("points", 0)
        chip = data.get("active_chip") or "None"

        return points, chip

    except Exception:
        return 0, "None"


def get_transfers(entry_id, gw):
    urls = [
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers-latest/",
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/"
    ]

    for url in urls:
        try:
            data = requests.get(url, timeout=8).json()

            if isinstance(data, list):
                if "transfers-latest" in url and data:
                    return data

                return [t for t in data if t.get("event") == gw]

        except Exception:
            pass

    return []


# ====================== HISTORY CHART ======================
def generate_history_chart():
    print("Fetching Overall Rank history...\n")

    fig = go.Figure()

    for entry_id, info in MANAGERS.items():
        gws = []
        overall_ranks = []

        for gw in range(1, 39):
            url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"

            try:
                resp = requests.get(url, timeout=10)

                if resp.status_code == 200:
                    data = resp.json()
                    history = data.get("entry_history", {})

                    overall_rank = history.get("overall_rank")

                    if overall_rank is not None:
                        gws.append(gw)
                        overall_ranks.append(int(overall_rank))

            except Exception:
                pass

        if gws:
            fig.add_trace(go.Scatter(
                x=gws,
                y=overall_ranks,
                mode="lines+markers",
                name=f"{info['team']} ({info['name']})",
                line=dict(width=3),
                marker=dict(size=6)
            ))

            print(f"Loaded {len(gws)} gameweeks for {info['team']}")
        else:
            print(f"No data for {info['team']}")

    if len(fig.data) > 0:
        fig.update_layout(
            xaxis_title="Gameweek",
            yaxis_title="Overall Rank",
            template="plotly_dark",
            autosize=True,
            height=680,
            margin=dict(l=70, r=20, t=70, b=60),
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            yaxis=dict(
                autorange="reversed",
                tickformat=","
            ),
            xaxis=dict(
                tickmode="linear",
                dtick=1,
                range=[1, 38]
            )
        )

        print("\nHistory chart created successfully!")

        return fig.to_html(
            full_html=False,
            include_plotlyjs="cdn",
            config={
                "responsive": True,
                "displayModeBar": False
            }
        )

    print("No history data loaded.")
    return '<p style="color:#888;">No history data loaded.</p>'


# ====================== INSIGHTS ======================
def safe_get(items, index, fallback=""):
    try:
        return items[index]
    except Exception:
        return fallback


def format_number(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def format_rank(value):
    try:
        return f"#{int(value):,}"
    except Exception:
        return f"#{value}"


def build_summary_html(standings, gw):
    if not standings:
        return ""

    leader = standings[0]
    second = standings[1] if len(standings) > 1 else standings[0]
    best_gw = max(standings, key=lambda s: s["gw"])
    leader_gap = max(leader["total"] - second["total"], 0)
    active_chips = [s for s in standings if s["chip"] != "None"]
    chip_items = "".join(
        f'<span class="chip-desk-pill">{s["manager"]}: {s["chip"]}</span>'
        for s in active_chips
    ) or '<span class="chip-desk-pill muted">No active chips</span>'

    return f"""
  <section class="summary-grid" aria-label="Executive summary">
    <article class="metric-card gw-card">
      <span class="metric-label">Live Race</span>
      <strong>GW{gw}</strong>
      <small>Season 25/26</small>
    </article>

    <article class="metric-card accent-gold">
      <span class="metric-label">Leader</span>
      <strong>{leader['emoji']} {leader['team']}</strong>
      <small>{leader['manager']} • {format_number(leader['total'])} pts</small>
    </article>

    <article class="metric-card">
      <span class="metric-label">Race Gap</span>
      <strong>{leader_gap} pts</strong>
      <small>1st to 2nd</small>
    </article>

    <article class="metric-card accent-cyan">
      <span class="metric-label">Best GW</span>
      <strong>{best_gw['gw']} pts</strong>
      <small>{best_gw['manager']} this week</small>
    </article>

    <article class="metric-card wide">
      <span class="metric-label">Chip Desk</span>
      <div class="chip-desk-list">{chip_items}</div>
      <small>Current gameweek activity</small>
    </article>
  </section>
"""


def get_insights(current_gw):
    next_gw = current_gw + 1

    insights = {
        34: {
            "title": "GW34 INSIGHT (Blank Gameweek)",
            "captains": [
                "Bruno Fernandes (MUN)",
                "Alexander Isak (NEW)",
                "Mohamed Salah (LIV)"
            ],
            "buys": [
                "Bruno Fernandes",
                "Alexander Isak",
                "Matheus Cunha"
            ],
            "sells": [
                "Arsenal assets",
                "Chelsea assets",
                "Man City assets"
            ],
            "note": "This is a Blank Gameweek for several big teams. Free Hit is very popular."
        },
        35: {
            "title": "GW35 INSIGHT (Title Race Heat)",
            "captains": [
                "Erling Haaland (MCI)",
                "Mohamed Salah (LIV)",
                "Bruno Fernandes (MUN)"
            ],
            "buys": [
                "Gabriel (ARS)",
                "Matheus Cunha (MUN)",
                "Morgan Gibbs-White (NFO)"
            ],
            "sells": [
                "Ollie Watkins",
                "Ivan Toney",
                "Man Utd Defenders"
            ],
            "note": "Focus on Arsenal and City assets for the title run-in, while Bruno Fernandes and Gibbs-White offer the best form for the final sprint."
        },
        36: {
        "title": "GW36 INSIGHT (The Double Down)",
        "captains": [
            "Erling Haaland (MCI)",
            "Phil Foden (MCI)",
            "Ismaïla Sarr (CRY)"
        ],
        "buys": [
            "Ismaïla Sarr (CRY)",
            "Josko Gvardiol (MCI)",
            "Dominic Calvert-Lewin (LEE)"
        ],
        "sells": [
            "Ollie Watkins (AVL)",
            "Cole Palmer (CHE)",
            "Newcastle Defenders"
        ],
        "note": "GW36 is a Double Gameweek for Manchester City and Crystal Palace. Triple-up on City assets is mandatory for the title charge, while Palace doublers like Sarr and Lacroix offer the best differential value. Sell Watkins and Palmer to fund these moves, as their single-fixture ceilings are lower than the doublers."
        }
      }

    data = insights.get(next_gw, {
        "title": f"GW{next_gw} INSIGHT",
        "captains": [
            "Mohamed Salah",
            "Erling Haaland",
            "Bruno Fernandes"
        ],
        "buys": [
            "Hot form players",
            "Good fixture picks",
            "Reliable starters"
        ],
        "sells": [
            "Underperforming assets",
            "Rotation risks",
            "Poor fixture players"
        ],
        "note": "Focus on good fixtures, nailed starters, and players with strong form."
    })
    clean_title = data["title"].split(" (", 1)[0]

    return f"""
  <section class="section-panel insight-box">
    <div class="section-heading">
      <h2>{clean_title}</h2>
    </div>

      <div class="insight-grid">
        <div class="insight-item">
          <strong>Best Captain Options</strong>
          <p>
          1. {safe_get(data['captains'], 0)}<br>
          2. {safe_get(data['captains'], 1)}<br>
          3. {safe_get(data['captains'], 2)}
          </p>
        </div>

        <div class="insight-item">
          <strong>Recommended Buys</strong>
          <p>
          1. {safe_get(data['buys'], 0)}<br>
          2. {safe_get(data['buys'], 1)}<br>
          3. {safe_get(data['buys'], 2)}
          </p>
        </div>

        <div class="insight-item">
          <strong>Recommended Sells</strong>
          <p>
          1. {safe_get(data['sells'], 0)}<br>
          2. {safe_get(data['sells'], 1)}<br>
          3. {safe_get(data['sells'], 2)}
          </p>
        </div>
      </div>

      <p class="insight-note">
        {data['note']}
      </p>

      <p class="insight-warning">
        The best advice would be to do the opposite of what the great Joey Yakeera suggests.
      </p>
  </section>
    """


# ====================== HTML TEMPLATE ======================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Clash of Captains - FPL Dashboard</title>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Orbitron:wght@600;800;900&display=swap');

    :root {{
      --bg: #070910;
      --panel: rgba(15, 20, 34, 0.84);
      --panel-strong: rgba(21, 28, 46, 0.94);
      --line: rgba(255, 255, 255, 0.12);
      --gold: #f5c84c;
      --cyan: #4de1ff;
      --rose: #ff4f7b;
      --green: #62e29a;
      --text: #f5f7fb;
      --muted: #aeb8c9;
    }}

    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background:
        linear-gradient(140deg, rgba(245,200,76,0.10), transparent 30%),
        linear-gradient(220deg, rgba(77,225,255,0.10), transparent 34%),
        var(--bg);
      color: var(--text);
      min-height: 100vh;
      overflow-x: hidden;
    }}

    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background:
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: 72px 72px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,0.95), transparent 72%);
      pointer-events: none;
      z-index: -1;
    }}

    .page-shell {{
      width: min(1240px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 52px;
    }}

    .hero {{
      min-height: 430px;
      display: block;
      padding: 36px 0 20px;
    }}

    .hero-copy,
    .section-panel,
    .metric-card,
    .card {{
      border: 1px solid var(--line);
      background: linear-gradient(145deg, rgba(20,27,45,0.88), rgba(9,12,22,0.92));
      box-shadow: 0 24px 80px rgba(0,0,0,0.30);
      backdrop-filter: blur(14px);
    }}

    .metric-card,
    .insight-item,
    .card {{
      transition:
        transform 180ms ease,
        border-color 180ms ease,
        box-shadow 180ms ease,
        background 180ms ease;
    }}

    .metric-card:hover,
    .insight-item:hover,
    .card:hover {{
      transform: translateY(-3px) scale(1.01);
      border-color: rgba(245,200,76,0.42);
      box-shadow: 0 28px 90px rgba(0,0,0,0.38);
      background: linear-gradient(145deg, rgba(25,33,55,0.92), rgba(10,14,25,0.96));
    }}

    .hero-copy {{
      position: relative;
      overflow: hidden;
      border-radius: 8px;
      padding: clamp(28px, 5vw, 54px);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 390px;
    }}

    .hero-copy::after {{
      content: '';
      position: absolute;
      inset: auto 0 0;
      height: 5px;
      background: linear-gradient(90deg, var(--gold), var(--cyan), var(--rose));
    }}

    .eyebrow,
    .section-heading span,
    .metric-label,
    .status-pill {{
      color: var(--cyan);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    h1 {{
      max-width: 820px;
      margin: 18px 0 18px;
      font-family: 'Orbitron', sans-serif;
      font-size: clamp(3rem, 8vw, 6.6rem);
      line-height: 0.92;
      font-weight: 900;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    .hero-copy p {{
      max-width: 680px;
      color: var(--muted);
      font-size: clamp(1rem, 2vw, 1.18rem);
      line-height: 1.65;
    }}

    .joey-dunk {{
      color: var(--rose);
      font-weight: 800;
      white-space: nowrap;
    }}

    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 34px;
    }}

    .status-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 36px;
      padding: 9px 12px;
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      color: var(--text);
    }}

    .status-pill.live {{
      color: #071016;
      background: var(--gold);
      border-color: transparent;
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 18px 0 26px;
    }}

    .metric-card {{
      border-radius: 8px;
      padding: 18px;
      min-height: 128px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}

    .metric-card.wide {{
      grid-column: span 2;
    }}

    .gw-card strong {{
      font-family: 'Orbitron', sans-serif;
      color: var(--gold);
      font-size: clamp(2.1rem, 4vw, 3.1rem);
    }}

    .metric-card strong {{
      display: block;
      margin: 12px 0 6px;
      font-size: clamp(1.25rem, 2vw, 1.8rem);
      line-height: 1.15;
    }}

    .metric-card small,
    .card small {{
      color: var(--muted);
    }}

    .chip-desk-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0 10px;
    }}

    .chip-desk-pill {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(77,225,255,0.10);
      color: var(--text);
      border: 1px solid rgba(77,225,255,0.24);
      font-size: 0.86rem;
      font-weight: 800;
      white-space: nowrap;
    }}

    .chip-desk-pill.muted {{
      color: var(--muted);
      border-color: rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.06);
    }}

    .accent-gold {{
      border-color: rgba(245,200,76,0.42);
    }}

    .accent-cyan {{
      border-color: rgba(77,225,255,0.42);
    }}

    .section-panel {{
      border-radius: 8px;
      padding: 24px;
      margin: 26px 0;
    }}

    .section-heading {{
      display: block;
      margin-bottom: 18px;
      text-align: left;
    }}

    .section-heading h2 {{
      font-size: clamp(1.35rem, 3vw, 2.15rem);
      line-height: 1.1;
      margin-top: 0;
    }}

    .league-table {{
      overflow-x: auto;
      padding: 0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 820px;
    }}

    th {{
      padding: 16px 18px;
      text-align: left;
      color: var(--gold);
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      background: rgba(255,255,255,0.04);
    }}

    td {{
      padding: 18px;
      border-top: 1px solid rgba(255,255,255,0.08);
      color: #edf2fb;
      font-size: 0.96rem;
    }}

    td.num,
    th.num {{
      text-align: right;
    }}

    tr.yours td {{
      background: rgba(245,200,76,0.07);
    }}

    tbody tr {{
      transition: background 160ms ease;
    }}

    tbody tr:hover td {{
      background: rgba(255,255,255,0.055);
    }}

    tbody tr.yours:hover td {{
      background: rgba(245,200,76,0.11);
    }}

    .rank-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 38px;
      height: 30px;
      border-radius: 999px;
      background: rgba(245,200,76,0.14);
      color: var(--gold);
      font-weight: 800;
    }}

    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(77,225,255,0.10);
      color: var(--cyan);
      font-size: 0.78rem;
      font-weight: 800;
      white-space: nowrap;
    }}

    .chip.none {{
      color: var(--muted);
      background: rgba(255,255,255,0.06);
    }}

    .history-chart-box .plotly-graph-div {{
      width: 100% !important;
      height: 660px !important;
      min-height: 0;
      border-radius: 8px;
      background: #090d16;
      overflow: hidden;
    }}

    .insight-grid,
    .container {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}

    .insight-item,
    .card {{
      border-radius: 8px;
      padding: 18px;
      background: rgba(255,255,255,0.045);
      border: 1px solid rgba(255,255,255,0.10);
    }}

    .insight-item strong {{
      display: block;
      color: var(--gold);
      margin-bottom: 10px;
      font-size: 0.92rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .insight-item p,
    .insight-note {{
      color: #d8e0ee;
      line-height: 1.55;
    }}

    .insight-note {{
      margin-top: 18px;
    }}

    .insight-warning {{
      margin-top: 16px;
      color: var(--rose);
      font-weight: 800;
    }}

    .transfers-section {{
      margin-top: 26px;
    }}

    .container {{
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    }}

    .card h2 {{
      margin-bottom: 18px;
      font-size: 1.05rem;
      letter-spacing: 0;
    }}

    .card h3 {{
      margin: 18px 0 12px;
      color: var(--cyan);
      font-size: 0.78rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    .card.yours {{
      border-color: rgba(245,200,76,0.48);
    }}

    .transfer-list {{
      list-style: none;
      padding: 0;
      display: grid;
      gap: 10px;
    }}

    .transfer-list li {{
      background: rgba(0,0,0,0.22);
      padding: 12px;
      border-radius: 8px;
      border-left: 3px solid var(--rose);
      line-height: 1.45;
    }}

    .transfer-list small {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.82rem;
    }}

    .transfer-out {{
      color: var(--rose);
      font-weight: 800;
    }}

    .transfer-in {{
      color: var(--green);
      font-weight: 800;
    }}

    .fade-in {{
      animation: riseIn 700ms ease both;
    }}

    @keyframes riseIn {{
      from {{
        opacity: 0;
        transform: translateY(12px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}

    @media (max-width: 768px) {{
      .page-shell {{
        width: min(100% - 20px, 1240px);
        padding-top: 10px;
      }}

      .hero {{
        min-height: auto;
        padding-top: 12px;
      }}

      .hero-copy,
      .section-panel {{
        padding: 18px;
      }}

      .hero-copy {{
        min-height: auto;
      }}

      .hero-meta {{
        margin-top: 22px;
      }}

      .status-pill {{
        width: 100%;
        justify-content: center;
        text-align: center;
      }}

      .summary-grid,
      .insight-grid,
      .container {{
        grid-template-columns: 1fr;
      }}

      .metric-card.wide {{
        grid-column: auto;
      }}

      .section-heading {{
        display: block;
      }}

      .history-chart-box .plotly-graph-div {{
        height: 500px !important;
      }}

      th,
      td {{
        padding: 13px 12px;
        font-size: 0.86rem;
      }}

      .metric-card:hover,
      .insight-item:hover,
      .card:hover {{
        transform: none;
      }}
    }}
  </style>
</head>

<body>
  <main class="page-shell">
    <section class="hero fade-in">
      <div class="hero-copy">
        <div>
          <div class="eyebrow">Fantasy Premier League rivalry desk</div>
          <h1>Clash of Captains</h1>
          <p>
            A private war room for the title race • Live standings, pressure points, and weekly swings that decide bragging rights.
            <span class="joey-dunk">(Joey is currently losing, like always)</span>
          </p>
        </div>

        <div class="hero-meta">
          <span class="status-pill live">Gameweek {gw}</span>
          <span class="status-pill">Last scanned: {timestamp}</span>
          <span class="status-pill">Updates 9 AM & 9 PM Eastern</span>
          <span class="status-pill">Manual refresh by WhatsApp request</span>
        </div>
      </div>
    </section>

    {summary_html}

    <section class="section-panel league-table">
      <div class="section-heading">
        <h2>Current standings</h2>
      </div>
      <table>
        <thead>
          <tr>
            <th>Pos</th>
            <th>Team</th>
            <th>Manager</th>
            <th class="num">Total</th>
            <th class="num">GW</th>
            <th class="num">Gap</th>
            <th class="num">Live Rank</th>
            <th>Chip</th>
          </tr>
        </thead>
        <tbody>{standings_html}</tbody>
      </table>
    </section>

    <section class="section-panel history-chart-box">
      <div class="section-heading">
        <h2>Historical rank progress</h2>
      </div>
      {history_chart_html}
    </section>

    {insight_html}

    <section class="transfers-section">
      <div class="section-heading">
        <span>Transfer Wire</span>
        <h2>Gameweek movement</h2>
      </div>
      <div class="container">
        {cards}
      </div>
    </section>
  </main>

  <script>
    function tuneHistoryChart() {{
      if (!window.Plotly) return;

      var chart = document.querySelector(".history-chart-box .plotly-graph-div");
      if (!chart) return;

      var mobile = window.matchMedia("(max-width: 768px)").matches;

      Plotly.restyle(chart, {{
        "line.width": mobile ? 2 : 3,
        "marker.size": mobile ? 4 : 6
      }});

      Plotly.relayout(chart, {{
        height: mobile ? 500 : 660,
        margin: mobile
          ? {{ l: 44, r: 8, t: 34, b: 46 }}
          : {{ l: 70, r: 20, t: 34, b: 60 }},
        font: {{ size: mobile ? 10 : 12 }},
        "title.font.size": mobile ? 13 : 18,
        "legend.orientation": mobile ? "h" : "v",
        "legend.x": mobile ? 0 : 0.01,
        "legend.y": mobile ? 1.16 : 0.99,
        "legend.xanchor": "left",
        "legend.yanchor": "top",
        "xaxis.dtick": mobile ? 4 : 1,
        "xaxis.title.text": mobile ? "GW" : "Gameweek",
        "yaxis.title.text": mobile ? "Rank" : "Overall Rank"
      }});
    }}

    window.addEventListener("load", tuneHistoryChart);
    window.addEventListener("resize", tuneHistoryChart);
  </script>
</body>
</html>"""


# ====================== CARD TEMPLATE ======================
CARD_TEMPLATE = """
<div class="card {yours_class}">
  <h2>
    {team} <small style="color:#888;">({manager})</small>
  </h2>

  <h3>Transfers this GW</h3>
  {transfers_html}
</div>
"""


# ====================== HTML GENERATION ======================
def generate_html(gw, players, history_chart_html):
    cards = []
    standings = []

    est = ZoneInfo("America/New_York")
    timestamp = datetime.now(est).strftime("%Y-%m-%d %I:%M %p %Z")

    for mid, info in MANAGERS.items():
        total_points, live_rank = get_manager_summary(mid)
        points, chip = get_picks(mid, gw)
        transfers = get_transfers(mid, gw)

        trans_lines = []

        for t in transfers:
            in_id = t.get("element_in")
            out_id = t.get("element_out")

            in_name = players.get(in_id, "Unknown")
            out_name = players.get(out_id, "Unknown")

            raw_time = t.get("time", "")
            clean_time = raw_time[:16].replace("T", " ") if raw_time else "N/A"

            trans_lines.append(
                f"<li><span class='transfer-out'>{out_name}</span> ↔ "
                f"<span class='transfer-in'>{in_name}</span><br>"
                f"<small>£0.0 → £0.0 • {clean_time}</small></li>"
            )

        transfers_html = (
            '<ul class="transfer-list">' + "".join(trans_lines) + "</ul>"
            if trans_lines
            else '<p style="color:#888;">No transfers this GW</p>'
        )

        cards.append(CARD_TEMPLATE.format(
            yours_class="yours" if info["yours"] else "",
            team=info["team"],
            manager=info["name"],
            transfers_html=transfers_html
        ))

        emojis = {
            "Sesko n Destroy": "🤖",
            "Fergie Time United": "🇪🇬",
            "BAKHAAT": "💩"
        }

        team_emoji = emojis.get(info["team"], "⚽")

        display_chip = "None"

        if chip and str(chip).lower() != "none":
            chip_map = {
                "wildcard": "WILDCARD",
                "freehit": "FREE HIT",
                "bboost": "BENCH BOOST",
                "3xc": "TRIPLE CAPTAIN"
            }

            display_chip = chip_map.get(str(chip).lower(), str(chip).upper())

        standings.append({
            "team": info["team"],
            "emoji": team_emoji,
            "manager": info["name"],
            "total": total_points,
            "gw": points,
            "rank": live_rank,
            "chip": display_chip,
            "yours": info["yours"]
        })

    standings.sort(key=lambda x: x["total"], reverse=True)

    standings_html = ""
    leader_total = standings[0]["total"] if standings else 0

    for i, s in enumerate(standings, 1):
        row_class = ' class="yours"' if s["yours"] else ""
        gap = leader_total - s["total"]
        gap_label = "Leader" if gap == 0 else f"-{gap}"
        chip_class = "chip none" if s["chip"] == "None" else "chip"

        standings_html += f"""
        <tr{row_class}>
          <td><span class="rank-badge">#{i}</span></td>
          <td>{s['emoji']} {s['team']}</td>
          <td>{s['manager']}</td>
          <td class="num"><strong>{format_number(s['total'])}</strong></td>
          <td class="num">{s['gw']}</td>
          <td class="num">{gap_label}</td>
          <td class="num">{format_rank(s['rank'])}</td>
          <td><span class="{chip_class}">{s['chip']}</span></td>
        </tr>"""

    insight_html = get_insights(gw)
    summary_html = build_summary_html(standings, gw)
    full_html = HTML_TEMPLATE.format(
        gw=gw,
        timestamp=timestamp,
        summary_html=summary_html,
        cards="\n".join(cards),
        standings_html=standings_html,
        insight_html=insight_html,
        history_chart_html=history_chart_html
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"\nDashboard updated successfully: {OUTPUT_FILE}")


# ====================== MAIN ======================
if __name__ == "__main__":
    print("Generating Clash of Captains Dashboard...")

    try:
        gw, players = get_bootstrap_data()

        print(f"Gameweek: {gw}")

        history_chart_html = generate_history_chart()
        generate_html(gw, players, history_chart_html)

    except Exception as e:
        print(f"Error: {e}")
