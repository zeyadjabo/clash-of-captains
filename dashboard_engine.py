import requests
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo
import plotly.graph_objects as go

# CONFIG
LEAGUE_ID = 966498
TRACKED_MANAGERS = {
    "Zee Jabo": {"name": "Zee", "emoji": "🤖", "yours": True},
    "Sam Wadea": {"name": "Sam", "emoji": "🇪🇬", "yours": False},
    "Jozeph Yakeera": {"name": "Joey", "emoji": "💩", "yours": False}
}

OUTPUT_FILE = "index.html"
ACTIVE_SEASON = "2026/2027"
ARCHIVE_SEASONS = ["2025/26", "2024/25", "2023/24"]
PAST_CHAMPIONS = [
    {"season": "2025/2026", "manager": "Zee", "points": 2223},
    {"season": "2024/2025", "manager": "Zee", "points": 2431},
    {"season": "2023/2024", "manager": "Sam", "points": 2350}
]

# Lucide icon paths (ISC); attribution is in assets/lucide-LICENSE.txt.
UI_ICON_PATHS = {
    "trophy": (
        '<path d="M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"/>'
        '<path d="M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"/>'
        '<path d="M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"/>'
        '<path d="M4 22h16"/>'
        '<path d="M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"/>'
        '<path d="M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"/>'
    ),
    "history": (
        '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
        '<path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>'
    ),
    "movement": (
        '<path d="m3 16 4 4 4-4"/><path d="M7 20V4"/>'
        '<path d="m21 8-4-4-4 4"/><path d="M17 4v16"/>'
    ),
}


def ui_icon(name):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
        + UI_ICON_PATHS[name] + '</svg>'
    )


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

        current_event = next((e for e in events if e["id"] == current_gw), {})
        gw_average = current_event.get("average_entry_score", 0)
        players = {p["id"]: p["web_name"] for p in data.get("elements", [])}

        print(f"Debug: GW {current_gw} detected")
        return current_gw, gw_average, players

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


def get_league_managers():
    tracked_names = set(TRACKED_MANAGERS)
    found = {}
    page = 1

    while tracked_names - set(found):
        url = (
            f"https://fantasy.premierleague.com/api/leagues-classic/{LEAGUE_ID}/"
            f"standings/?page_standings={page}"
        )

        try:
            data = requests.get(url, timeout=10).json()
        except Exception as e:
            raise Exception(f"League standings failed: {e}")

        standings = data.get("standings", {})
        results = standings.get("results", [])

        for row in results:
            player_name = row.get("player_name", "")

            if player_name in tracked_names:
                profile = TRACKED_MANAGERS[player_name]
                found[player_name] = {
                    "id": row.get("entry"),
                    "name": profile["name"],
                    "full_name": player_name,
                    "team": row.get("entry_name", "Unknown team"),
                    "emoji": profile["emoji"],
                    "yours": profile["yours"],
                    "league_rank": row.get("rank"),
                    "last_rank": row.get("last_rank"),
                    "total": row.get("total", 0),
                    "event_total": row.get("event_total", 0)
                }

        has_next = standings.get("has_next", False)

        if not has_next:
            break

        page += 1

    missing = tracked_names - set(found)

    if missing:
        raise Exception(
            "Could not find tracked managers in league "
            f"{LEAGUE_ID}: {', '.join(sorted(missing))}"
        )

    managers = list(found.values())
    managers.sort(key=lambda m: int(m.get("league_rank") or 999999))

    print(f"Loaded {len(managers)} tracked managers from league {LEAGUE_ID}")
    return managers


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


def get_manager_past_seasons(entry_id):
    try:
        data = requests.get(
            f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/",
            timeout=8
        ).json()
    except Exception:
        return {}

    return {
        season.get("season_name"): season
        for season in data.get("past", [])
        if season.get("season_name")
    }


# ====================== HISTORY CHART ======================
def generate_history_chart(managers, current_gw):
    print("Fetching Overall Rank history...\n")

    fig = go.Figure()
    display_until_gw = min(current_gw + 5, 38)

    for info in managers:
        entry_id = info["id"]
        gws = []
        overall_ranks = []

        for gw in range(1, current_gw + 1):
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
            margin=dict(l=70, r=20, t=96, b=60),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.04,
                xanchor="left",
                x=0
            ),
            yaxis=dict(
                autorange="reversed",
                tickformat=","
            ),
            xaxis=dict(
                tickmode="linear",
                dtick=1,
                range=[1, max(display_until_gw, 2)]
            )
        )

        print("\nHistory chart created successfully!")

        chart_json = fig.to_json().replace("</", "<\\/")

        return f"""
        <div id="history-chart" class="plotly-graph-div" style="height:680px; width:100%;"></div>
        <script id="history-chart-json" type="application/json">{chart_json}</script>
        """

    print("No history data loaded.")
    return '<p class="empty-chart-note">Rank history starts once GW1 data is fully processed.</p>'


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


def build_trophy_cabinet_html():
    rows = []
    latest_champion = max(PAST_CHAMPIONS, key=lambda champion: champion["season"], default=None)
    champion_note = (
        f'<small class="champion-note">Champion: {escape(latest_champion["manager"])}</small>'
        if latest_champion else ""
    )
    champion_label = (
        f"Trophy Cabinet. Reigning champion: {latest_champion['manager']}, {latest_champion['season']}."
        if latest_champion else "Trophy Cabinet"
    )

    for champion in PAST_CHAMPIONS:
        points = champion.get("points")
        rows.append(
            "<tr>"
            f"<td>{escape(champion['season'])}</td>"
            f"<td>{escape(champion['manager'])}</td>"
            f"<td>{format_number(points) if points else '-'}</td>"
            "</tr>"
        )

    return f"""
          <details class="trophy-cabinet" name="rivalry-history">
            <summary data-history-view="trophies" aria-controls="trophy-cabinet-panel" aria-label="{escape(champion_label)}">
              {ui_icon('trophy')}
              <span class="history-trigger-text"><span>Trophy Cabinet</span>{champion_note}</span>
            </summary>
            <div class="trophy-cabinet-panel" id="trophy-cabinet-panel">
              <span>Historical champions</span>
              <table>
                <thead>
                  <tr>
                    <th>Season</th>
                    <th>Champion</th>
                    <th>Points</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(rows)}
                </tbody>
              </table>
              <p>Back-to-back champion. Kai Laa Nansaa.</p>
            </div>
          </details>
"""


def build_rivalry_archive_html(managers):
    histories = {
        manager["name"]: get_manager_past_seasons(manager["id"])
        for manager in managers
    }
    columns = ["Zee", "Sam", "Joey"]
    rows = []
    mobile_cards = []

    for season in ARCHIVE_SEASONS:
        cells = []
        mobile_entries = []

        for manager in columns:
            record = histories.get(manager, {}).get(season)

            if record:
                rank = format_rank(record["rank"])
                points = format_number(record["total_points"])
                rank_percentage = record.get("rank_percentage")
                percentage_label = (
                    f"Top {rank_percentage}%"
                    if rank_percentage not in (None, "")
                    else "Top % unavailable"
                )
                cells.append(
                    "<td>"
                    f"<strong>{escape(rank)}</strong>"
                    f"<small>{escape(points)} pts</small>"
                    f"<small>{escape(percentage_label)}</small>"
                    "</td>"
                )
                mobile_entries.append(
                    "<div>"
                    f"<strong>{escape(manager)}</strong>"
                    f"<span>{escape(rank)}</span>"
                    f"<small>{escape(points)} pts • {escape(percentage_label)}</small>"
                    "</div>"
                )
            else:
                cells.append("<td>No record</td>")
                mobile_entries.append(
                    "<div>"
                    f"<strong>{escape(manager)}</strong>"
                    "<span>No record</span>"
                    "</div>"
                )

        rows.append(
            "<tr>"
            f"<td>{escape(season.replace('/', '/20'))}</td>"
            f"{''.join(cells)}"
            "</tr>"
        )
        mobile_cards.append(
            "<article class=\"archive-season-card\">"
            f"<h3>{escape(season.replace('/', '/20'))}</h3>"
            f"{''.join(mobile_entries)}"
            "</article>"
        )

    return f"""
          <details class="rivalry-archive" name="rivalry-history">
            <summary data-history-view="archive" aria-controls="rivalry-archive-panel">
              {ui_icon('history')}<span class="history-trigger-text">Rivalry Archive</span>
            </summary>
            <div class="rivalry-archive-panel" id="rivalry-archive-panel">
              <span>Historical overall ranks, points, and percentile</span>
              <table>
                <thead>
                  <tr>
                    <th>Season</th>
                    <th>Zee</th>
                    <th>Sam</th>
                    <th>Joey</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(rows)}
                </tbody>
              </table>
              <div class="archive-mobile-list">
                {''.join(mobile_cards)}
              </div>
              <p>Missing seasons mean FPL does not expose that season for the current account ID.</p>
            </div>
          </details>
"""


def build_summary_html(standings, gw, gw_average):
    if not standings:
        return ""

    leader = standings[0]
    second = standings[1] if len(standings) > 1 else standings[0]
    best_gw = max(standings, key=lambda s: s["gw"])
    leader_gap = max(leader["total"] - second["total"], 0)
    active_chips = [s for s in standings if s["chip"] != "None"]
    chip_items = "".join(
        f'<span class="chip-desk-pill">{escape(s["manager"])}: {escape(s["chip"])}</span>'
        for s in active_chips
    ) or '<span class="chip-desk-pill muted">No active chips</span>'

    return f"""
  <section class="summary-grid" aria-label="Executive summary">
    <article class="metric-card gw-card">
      <span class="metric-label">Live Race</span>
      <strong>GW{gw}</strong>
      <small>Season {ACTIVE_SEASON}</small>
    </article>

    <article class="metric-card accent-gold">
      <span class="metric-label">Leader</span>
      <strong>{leader['emoji']} {escape(leader['team'])}</strong>
      <small>{escape(leader['manager'])} • {format_number(leader['total'])} pts</small>
    </article>

    <article class="metric-card">
      <span class="metric-label">Race Gap</span>
      <strong>{leader_gap} pts</strong>
      <small>1st to 2nd</small>
    </article>

    <article class="metric-card accent-cyan">
      <span class="metric-label">Best GW</span>
      <strong>{best_gw['gw']} pts</strong>
      <small>{escape(best_gw['manager'])} this week</small>
    </article>

    <article class="metric-card">
      <span class="metric-label">GW Average</span>
      <strong>{gw_average} pts</strong>
      <small>FPL benchmark</small>
    </article>

    <article class="metric-card wide">
      <span class="metric-label">Chip Desk</span>
      <div class="chip-desk-list">{chip_items}</div>
      <small>Current gameweek activity</small>
    </article>
  </section>
"""


def get_insights(current_gw):
    if current_gw >= 38:
        return """
  <section class="section-panel insight-box">
    <div class="section-heading">
      <h2>SEASON CONCLUSION</h2>
    </div>

      <div class="insight-grid season-conclusion-grid">
        <div class="insight-item">
          <strong>Final Whistle</strong>
          <p>
          No more Gameweeks. No more excuses. The spreadsheets and data analytics are retired, the season is officially dead, and I’m sitting on top collecting my bragging rights like rent.<br><br>
          Sam went full “ya basha” mode again, consulting every Egyptian YouTuber known to man, but even the Pharaohs curse couldn’t save him for the second year in a row. Meanwhile Joey’s still stuck in the stone age, resisting AI and advanced data like it’s the plague and cheering for Sam to win instead of putting in the work himself for the third year running. Absolute disaster.<br><br>
          Season closed. My league title is secured. Rivalries remain open. Thanks for watching.
          </p>
        </div>

        <div class="insight-item">
          <strong>Season Verdict</strong>
          <p>
          Credit where it’s due: Sam turned up the intensity in the final leg and made it fun to play. But Joey? Man’s been providing elite motivation all season and nothing gets me going like the desire to squash him like a bug. Receipts are being filed and screenshotted for group chat use all summer.
          </p>
        </div>
      </div>

      <p class="insight-note">
        Season closed. Rivalries remain open.
      </p>

      <p class="insight-warning">
        The best advice remains unchanged: do the opposite of what the great Joey Yakeera suggests. Not only in FPL but in life in general. FFS, the guy lives in California, that tells you a lot lol.
      </p>
  </section>
        """

    next_gw = current_gw + 1

    insights = {
        2: {
            "title": "GW2 INSIGHT (Opening Moves)",
            "captains": [
                "Early form premiums",
                "Reliable home-fixture stars",
                "Penalty takers with strong minutes"
            ],
            "buys": [
                "Nailed starters",
                "Emerging bandwagons",
                "Underpriced attackers"
            ],
            "sells": [
                "Minutes risks",
                "One-week punts",
                "Players already testing patience"
            ],
            "note": "The first week is information, not a full personality change. Back the strong minutes, watch the price moves, and remember that Joey panicking early is usually the market signal we all needed."
        },
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
        },
        37: {
        "title": "GW37 INSIGHT (Penultimate Push)",
        "captains": [
            "Bukayo Saka (ARS)",
            "Bruno Fernandes (MUN)",
            "Erling Haaland (MCI)"
        ],
        "buys": [
            "Viktor Gyokeres (ARS)",
            "Gabriel Magalhães (ARS)",
            "Igor Thiago (BRE)"
        ],
        "sells": [
            "Cole Palmer (CHE)",
            "Ollie Watkins (AVL)",
            "Crystal Palace assets"
        ],
        "note": "GW37 is a big single gameweek with several favourable fixtures. Arsenal at home to Burnley is the standout, so loading up on Bottlers attackers and defenders is key. Bruno has a great home fixture vs Nottingham Forest. Haaland remains the safe premium option. Sell players with tougher fixtures or rotation risks as we head into the final week."
        },
        38: {
        "title": "GW38 INSIGHT (The Grand Finale)",
        "captains": [
            "Erling Haaland (MCI)",
            "Viktor Gyokeres (ARS)",
            "Jarrod Bowen (WHU)"
        ],
        "buys": [
            "Jarrod Bowen (WHU)",
            "Kiernan Dewsbury-Hall (EVE)",
            "Pedro Porro (TOT)"
        ],
        "sells": [
            "Bournemouth assets",
            "Burnley assets",
            "Sunderland assets"
        ],
        "note": "GW38 is historically a high-scoring curtain-closer where chasing upside is the priority. Manchester City host Aston Villa in a massive final-day fixture, keeping Haaland as the premier captaincy shield. Arsenal travel to Crystal Palace, who have a European final just three days later—making Gyokeres and Saka prime targets for heavy investment. For mini-league differentials, look to West Ham at home to Leeds (Bowen), an in-form Everton pushing for Europe (Dewsbury-Hall), or Spurs fighting for position against Everton (Porro). Clear out players with nothing left to play for or brutal final-day fixtures."
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
  <meta name="description" content="Track the Clash of Captains Fantasy Premier League mini-league with live standings, weekly transfers, rank history, and captain insights.">
  <title>Clash of Captains - FPL Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" onload="this.onload=null;this.rel='stylesheet'">
  <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"></noscript>

  <style>
    :root {{
      color-scheme: dark;
      --bg: #101214;
      --panel: #191c20;
      --panel-strong: #23272c;
      --line: rgba(255, 255, 255, 0.12);
      --gold: #ecc65b;
      --cyan: #65d5e9;
      --rose: #f18a9f;
      --green: #82d4a5;
      --text: #f1f4f5;
      --muted: #bac2c8;
      --manager-zee: #65d5e9;
      --manager-sam: #f29d8b;
      --manager-joey: #92d9b1;
      --font-body: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      --text-xs: 0.75rem;
      --text-sm: 0.875rem;
      --text-body: 1rem;
      --text-section: 1.5rem;
      --text-metric: 1.75rem;
      --text-display: 3.75rem;
      --space-1: 4px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --space-5: 24px;
      --space-6: 32px;
      --space-7: 48px;
      --page-gutter: var(--space-5);
      --radius: 6px;
      --shadow-surface: 0 4px 16px rgba(0, 0, 0, 0.12);
      --shadow-hover: 0 8px 24px rgba(0, 0, 0, 0.20);
    }}

    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      font-family: var(--font-body);
      font-size: var(--text-body);
      line-height: 1.5;
      letter-spacing: 0;
      font-variant-numeric: tabular-nums;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}

    button,
    input,
    select,
    textarea {{
      font: inherit;
      color: inherit;
    }}

    a,
    button,
    summary {{
      touch-action: manipulation;
    }}

    :focus-visible {{
      outline: 2px solid var(--cyan);
      outline-offset: 3px;
    }}

    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip-path: inset(50%);
      white-space: nowrap;
      border: 0;
    }}

    [data-manager="zee"] {{
      --manager-color: var(--manager-zee);
    }}

    [data-manager="sam"] {{
      --manager-color: var(--manager-sam);
    }}

    [data-manager="joey"] {{
      --manager-color: var(--manager-joey);
    }}

    .page-shell {{
      width: min(1240px, calc(100% - 2 * var(--page-gutter)));
      margin: 0 auto;
      padding: var(--space-5) 0 var(--space-7);
    }}

    .masthead {{
      position: relative;
      z-index: 20;
      display: grid;
      gap: var(--space-3);
      padding: var(--space-2) 0 var(--space-5);
      border-bottom: 1px solid var(--line);
    }}

    .section-panel,
    .metric-card,
    .card {{
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow-surface);
    }}

    .interactive-surface {{
      transition:
        transform 180ms ease,
        border-color 180ms ease,
        box-shadow 180ms ease;
    }}

    @media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference) {{
      .interactive-surface:hover {{
        transform: translateY(-2px);
        border-color: var(--cyan);
        box-shadow: var(--shadow-hover);
      }}
    }}

    .masthead-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-3);
    }}

    .masthead-brand {{
      min-width: 0;
    }}

    .eyebrow,
    .section-heading span,
    .metric-label {{
      color: var(--cyan);
      font-size: var(--text-xs);
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    .masthead h1 {{
      margin-top: var(--space-1);
      font-family: var(--font-body);
      font-size: 2rem;
      line-height: 1.15;
      font-weight: 800;
      letter-spacing: 0;
    }}

    .gameweek-label {{
      flex: 0 0 auto;
      padding: var(--space-2) var(--space-3);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      font-size: var(--text-sm);
      font-weight: 800;
      color: var(--gold);
      background: var(--panel);
    }}

    .joey-dunk {{
      color: var(--rose);
      font-weight: 800;
      white-space: nowrap;
    }}

    .masthead-meta {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: var(--space-1) var(--space-4);
      color: var(--muted);
      font-size: var(--text-xs);
    }}

    .snapshot-status {{
      min-width: 0;
      overflow-wrap: anywhere;
    }}

    .masthead-nav {{
      position: relative;
      display: flex;
      flex-wrap: wrap;
      align-items: stretch;
      gap: var(--space-2);
    }}

    .masthead-link {{
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      min-height: 44px;
      padding: var(--space-2) var(--space-3);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: transparent;
      color: var(--text);
      font-size: var(--text-sm);
      font-weight: 600;
      text-decoration: none;
    }}

    .masthead-nav svg {{
      width: 16px;
      height: 16px;
      flex: 0 0 16px;
    }}

    /* Anchor native panels to the whole nav, not a narrow trigger. */
    .trophy-cabinet,
    .rivalry-archive {{
      position: static;
    }}

    .trophy-cabinet summary,
    .rivalry-archive summary {{
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      min-height: 44px;
      padding: var(--space-2) var(--space-3);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: transparent;
      color: var(--text);
      cursor: pointer;
      font-size: var(--text-sm);
      font-weight: 600;
      letter-spacing: 0;
      list-style: none;
    }}

    .history-trigger-text {{
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 0 var(--space-3);
      min-width: 0;
      text-align: left;
    }}

    .champion-note {{
      color: var(--gold);
      font-size: var(--text-xs);
      font-weight: 500;
      overflow-wrap: anywhere;
    }}

    .masthead-link:hover,
    .trophy-cabinet summary:hover,
    .rivalry-archive summary:hover {{
      background: var(--panel-strong);
    }}

    .trophy-cabinet summary::-webkit-details-marker,
    .rivalry-archive summary::-webkit-details-marker {{
      display: none;
    }}

    .trophy-cabinet summary::after,
    .rivalry-archive summary::after {{
      content: '▾';
      margin-left: auto;
      font-size: 0.82rem;
    }}

    .trophy-cabinet[open] summary::after,
    .rivalry-archive[open] summary::after {{
      content: '▴';
    }}

    .trophy-cabinet-panel,
    .rivalry-archive-panel {{
      position: absolute;
      left: 0;
      right: auto;
      top: calc(100% + var(--space-2));
      z-index: 30;
      width: min(520px, 100%);
      padding: 14px;
      border: 1px solid rgba(245,200,76,0.32);
      border-radius: 8px;
      background: rgba(8, 11, 19, 0.98);
      box-shadow: 0 24px 70px rgba(0,0,0,0.45);
    }}

    .trophy-cabinet-panel {{
      width: min(620px, 100%);
    }}

    .trophy-cabinet-panel > span,
    .rivalry-archive-panel > span {{
      display: block;
      margin-bottom: 12px;
      color: var(--cyan);
      font-size: 0.68rem;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    .trophy-cabinet p {{
      margin-top: 12px;
      color: var(--rose);
      font-size: 0.82rem;
      font-weight: 800;
      line-height: 1.35;
    }}

    .trophy-cabinet table,
    .rivalry-archive table {{
      width: 100%;
      min-width: 0;
      border-collapse: collapse;
    }}

    .trophy-cabinet th,
    .trophy-cabinet td,
    .rivalry-archive th,
    .rivalry-archive td {{
      padding: 9px 8px;
      border-top: 1px solid rgba(255,255,255,0.08);
      font-size: 0.82rem;
      text-align: left;
      white-space: nowrap;
    }}

    .trophy-cabinet th,
    .rivalry-archive th {{
      color: var(--gold);
      background: transparent;
      letter-spacing: 0;
    }}

    .rivalry-archive td strong {{
      display: block;
      color: var(--text);
      font-size: 0.84rem;
    }}

    .rivalry-archive td small {{
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 0.74rem;
    }}

    .archive-mobile-list {{
      display: none;
    }}

    .rivalry-archive p {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.45;
    }}

    .summary-grid {{
      position: relative;
      z-index: 1;
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
      font-family: var(--font-body);
      color: var(--gold);
      font-size: 2rem;
    }}

    .metric-card strong {{
      display: block;
      margin: 12px 0 6px;
      font-size: var(--text-metric);
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

    .previous-champion-card {{
      border-color: rgba(245,200,76,0.30);
      background: linear-gradient(145deg, rgba(35,28,15,0.78), rgba(10,14,25,0.94));
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
      font-size: var(--text-section);
      line-height: 1.25;
      margin-top: 0;
    }}

    .league-table {{
      overflow-x: auto;
      padding: 0;
    }}

    .standings-mobile-list {{
      display: none;
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
      letter-spacing: 0;
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

    .empty-chart-note {{
      color: var(--muted);
      padding: 36px 18px;
      border: 1px dashed rgba(255,255,255,0.16);
      border-radius: 8px;
      background: rgba(255,255,255,0.035);
      text-align: center;
    }}

    .insight-grid,
    .container {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}

    .season-conclusion-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
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
      letter-spacing: 0;
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

    .dashboard-footer {{
      margin-top: var(--space-7);
      padding-top: var(--space-5);
      border-top: 1px solid var(--line);
      color: var(--muted);
    }}

    .rivalry-description {{
      max-width: 720px;
      font-size: var(--text-sm);
      line-height: 1.65;
    }}

    .refresh-information {{
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2) var(--space-5);
      margin-top: var(--space-3);
      list-style: none;
      font-size: var(--text-xs);
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
      letter-spacing: 0;
      text-transform: uppercase;
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

    @media (prefers-reduced-motion: reduce) {{
      *,
      *::before,
      *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }}
    }}

    @media (max-width: 768px) {{
      :root {{
        --page-gutter: var(--space-4);
        --text-display: 2.25rem;
        --text-section: 1.25rem;
        --text-metric: 1.5rem;
      }}

      .page-shell {{
        padding-top: var(--space-3);
      }}

      .masthead {{
        padding-top: var(--space-1);
        padding-bottom: var(--space-4);
      }}

      .section-panel {{
        padding: 18px;
      }}

      .masthead h1 {{
        font-size: 1.5rem;
      }}

      .gameweek-label {{
        padding: var(--space-1) var(--space-2);
      }}

      .masthead-nav {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .masthead-link {{
        min-height: 52px;
        padding: var(--space-2);
        font-size: var(--text-xs);
      }}

      .trophy-cabinet {{
        grid-column: 1 / -1;
      }}

      .rivalry-archive summary {{
        min-height: 52px;
      }}

      .trophy-cabinet,
      .rivalry-archive,
      .trophy-cabinet summary,
      .rivalry-archive summary {{
        width: 100%;
      }}

      .trophy-cabinet summary,
      .rivalry-archive summary {{
        gap: 6px;
        padding: var(--space-2);
        font-size: var(--text-xs);
      }}

      .trophy-cabinet-panel,
      .rivalry-archive-panel {{
        left: 0;
        right: auto;
        width: 100%;
      }}

      .trophy-cabinet-panel,
      .rivalry-archive-panel {{
        overflow-x: auto;
      }}

      .rivalry-archive table {{
        display: none;
      }}

      .archive-mobile-list {{
        display: grid;
        gap: 10px;
      }}

      .archive-season-card {{
        display: grid;
        gap: 10px;
        padding: 12px;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 8px;
        background: rgba(255,255,255,0.04);
      }}

      .archive-season-card h3 {{
        margin: 0;
        color: var(--gold);
        font-size: 0.82rem;
        letter-spacing: 0;
      }}

      .archive-season-card div {{
        display: grid;
        grid-template-columns: 54px minmax(0, 1fr);
        gap: 4px 10px;
        align-items: baseline;
      }}

      .archive-season-card strong {{
        color: var(--cyan);
        font-size: 0.78rem;
      }}

      .archive-season-card span {{
        color: var(--text);
        font-size: 0.9rem;
        font-weight: 800;
      }}

      .archive-season-card small {{
        grid-column: 2;
        color: var(--muted);
        font-size: 0.76rem;
      }}

      .summary-grid,
      .insight-grid,
      .container {{
        grid-template-columns: 1fr;
      }}

      .league-table {{
        overflow-x: visible;
      }}

      .league-table table {{
        display: none;
      }}

      .standings-mobile-list {{
        display: grid;
        gap: 12px;
      }}

      .standing-mobile-card {{
        display: grid;
        gap: 14px;
        padding: 14px;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 8px;
        background: rgba(255,255,255,0.045);
      }}

      .standing-mobile-card.yours {{
        border-color: rgba(245,200,76,0.44);
        background: rgba(245,200,76,0.075);
      }}

      .standing-mobile-head {{
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 10px;
        align-items: center;
      }}

      .standing-mobile-team {{
        min-width: 0;
      }}

      .standing-mobile-team strong {{
        display: block;
        color: var(--text);
        font-size: 0.98rem;
        line-height: 1.2;
      }}

      .standing-mobile-team small {{
        display: block;
        margin-top: 3px;
        color: var(--muted);
        font-size: 0.78rem;
      }}

      .standing-mobile-stats {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}

      .standing-mobile-stat {{
        min-height: 62px;
        padding: 10px;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        background: rgba(0,0,0,0.18);
      }}

      .standing-mobile-stat span {{
        display: block;
        color: var(--cyan);
        font-size: 0.64rem;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }}

      .standing-mobile-stat strong {{
        display: block;
        margin-top: 6px;
        color: var(--text);
        font-size: 0.96rem;
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
    <header class="hero masthead fade-in" aria-label="League overview">
      <div class="masthead-top">
        <div class="masthead-brand">
          <p class="eyebrow">Fantasy Premier League rivalry desk</p>
          <h1>Clash of Captains</h1>
        </div>
        <span class="gameweek-label" data-gameweek="{gw}">GW{gw}</span>
      </div>

      <div class="masthead-meta">
        <p class="snapshot-status">Last scanned: <time datetime="{timestamp_iso}">{timestamp}</time></p>
        <span class="masthead-season" data-season="{season}">Season {season}</span>
      </div>

      <nav class="masthead-nav" aria-label="Rivalry navigation">
        {trophy_html}
        {archive_html}
        <a class="masthead-link" href="#gameweek-movement">{movement_icon}<span>Gameweek movement</span></a>
      </nav>
    </header>

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
      <div class="standings-mobile-list">
        {standings_mobile_html}
      </div>
    </section>

    <section class="section-panel history-chart-box">
      <div class="section-heading">
        <h2>Historical rank progress</h2>
      </div>
      {history_chart_html}
    </section>

    <section class="transfers-section" id="gameweek-movement" tabindex="-1" aria-labelledby="movement-heading">
      <div class="section-heading">
        <span>Transfer Wire</span>
        <h2 id="movement-heading">Gameweek movement</h2>
      </div>
      <div class="container">
        {cards}
      </div>
    </section>

    <footer class="dashboard-footer">
      <p class="rivalry-description">A private war room for the title race • Live standings, pressure points, and weekly swings that decide bragging rights.</p>
      <ul class="refresh-information">
        <li>Updates 9 AM & 9 PM Eastern</li>
        <li>Manual refresh by WhatsApp request</li>
      </ul>
    </footer>
  </main>

  <script>
    var plotlyLoadPromise;

    function getHistoryChartLayout() {{
      var mobile = window.matchMedia("(max-width: 768px)").matches;

      return {{
        height: mobile ? 500 : 660,
        margin: mobile
          ? {{ l: 44, r: 8, t: 76, b: 46 }}
          : {{ l: 70, r: 20, t: 96, b: 60 }},
        font: {{ size: mobile ? 10 : 12 }},
        "title.font.size": mobile ? 13 : 18,
        "legend.orientation": "h",
        "legend.x": 0,
        "legend.y": mobile ? 1.14 : 1.04,
        "legend.xanchor": "left",
        "legend.yanchor": "bottom",
        "xaxis.dtick": mobile ? 4 : 1,
        "xaxis.title.text": mobile ? "GW" : "Gameweek",
        "yaxis.title.text": mobile ? "Rank" : "Overall Rank"
      }};
    }}

    function tuneHistoryChart() {{
      if (!window.Plotly) return;

      var chart = document.querySelector(".history-chart-box .plotly-graph-div");
      if (!chart || !chart.dataset.rendered) return;

      var mobile = window.matchMedia("(max-width: 768px)").matches;

      Plotly.restyle(chart, {{
        "line.width": mobile ? 2 : 3,
        "marker.size": mobile ? 4 : 6
      }});

      Plotly.relayout(chart, getHistoryChartLayout());
    }}

    function loadPlotly() {{
      if (window.Plotly) return Promise.resolve();
      if (plotlyLoadPromise) return plotlyLoadPromise;

      plotlyLoadPromise = new Promise(function(resolve, reject) {{
        var script = document.createElement("script");
        script.src = "https://cdn.plot.ly/plotly-4.0.0.min.js";
        script.defer = true;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      }});

      return plotlyLoadPromise;
    }}

    function renderHistoryChart() {{
      var chart = document.querySelector(".history-chart-box .plotly-graph-div");
      var payload = document.getElementById("history-chart-json");
      if (!chart || !payload || chart.dataset.rendered) return;

      loadPlotly().then(function() {{
        var figure = JSON.parse(payload.textContent);
        figure.layout = Object.assign({{}}, figure.layout, getHistoryChartLayout());

        Plotly.newPlot(chart, figure.data, figure.layout, {{
          responsive: true,
          displayModeBar: false
        }}).then(function() {{
          chart.dataset.rendered = "true";
          tuneHistoryChart();
        }});
      }});
    }}

    function initHistoryChart() {{
      var chart = document.querySelector(".history-chart-box .plotly-graph-div");
      if (!chart) return;

      if ("IntersectionObserver" in window) {{
        var observer = new IntersectionObserver(function(entries) {{
          entries.forEach(function(entry) {{
            if (entry.isIntersecting) {{
              observer.disconnect();
              renderHistoryChart();
            }}
          }});
        }}, {{ rootMargin: "320px 0px" }});

        observer.observe(chart);
        return;
      }}

      renderHistoryChart();
    }}

    function syncHeroDropdowns() {{
      var dropdowns = document.querySelectorAll(".trophy-cabinet, .rivalry-archive");

      dropdowns.forEach(function(dropdown) {{
        dropdown.addEventListener("toggle", function() {{
          if (!dropdown.open) return;

          dropdowns.forEach(function(otherDropdown) {{
            if (otherDropdown !== dropdown) {{
              otherDropdown.open = false;
            }}
          }});
        }});
      }});
    }}
    window.addEventListener("load", initHistoryChart);
    window.addEventListener("load", syncHeroDropdowns);
    window.addEventListener("resize", tuneHistoryChart);
  </script>
</body>
</html>"""


# ====================== CARD TEMPLATE ======================
CARD_TEMPLATE = """
<div class="card">
  <h2>
    {team} <small style="color:#888;">({manager})</small>
  </h2>

  <h3>Transfers this GW</h3>
  {transfers_html}
</div>
"""


# ====================== HTML GENERATION ======================
def generate_html(gw, gw_average, players, managers, history_chart_html):
    cards = []
    standings = []

    est = ZoneInfo("America/New_York")
    scan_time = datetime.now(est)
    timestamp = scan_time.strftime("%Y-%m-%d %I:%M %p %Z")
    timestamp_iso = scan_time.isoformat(timespec="minutes")

    for info in managers:
        entry_id = info["id"]
        _, live_rank = get_manager_summary(entry_id)
        total_points = info["total"]
        points, chip = get_picks(entry_id, gw)

        if info["event_total"]:
            points = info["event_total"]

        transfers = get_transfers(entry_id, gw)

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
            team=escape(info["team"]),
            manager=escape(info["name"]),
            transfers_html=transfers_html
        ))

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
            "emoji": info["emoji"],
            "manager": info["name"],
            "full_name": info["full_name"],
            "total": total_points,
            "gw": points,
            "rank": live_rank,
            "league_rank": info["league_rank"],
            "chip": display_chip,
            "yours": info["yours"]
        })

    standings.sort(key=lambda x: int(x.get("league_rank") or 999999))

    standings_html = ""
    standings_mobile_html = ""
    leader_total = standings[0]["total"] if standings else 0

    for index, s in enumerate(standings, 1):
        row_class = ' class="yours"' if s["yours"] else ""
        gap = leader_total - s["total"]
        gap_label = "Leader" if gap == 0 else f"-{gap}"
        chip_class = "chip none" if s["chip"] == "None" else "chip"
        local_rank = index

        standings_html += f"""
        <tr{row_class}>
          <td><span class="rank-badge">#{local_rank}</span></td>
          <td>{s['emoji']} {escape(s['team'])}</td>
          <td>{escape(s['manager'])}</td>
          <td class="num"><strong>{format_number(s['total'])}</strong></td>
          <td class="num">{s['gw']}</td>
          <td class="num">{gap_label}</td>
          <td class="num">{format_rank(s['rank'])}</td>
          <td><span class="{chip_class}">{s['chip']}</span></td>
        </tr>"""

        standings_mobile_html += f"""
        <article class="standing-mobile-card{' yours' if s['yours'] else ''}">
          <div class="standing-mobile-head">
            <span class="rank-badge">#{local_rank}</span>
            <div class="standing-mobile-team">
              <strong>{s['emoji']} {escape(s['team'])}</strong>
              <small>{escape(s['manager'])}</small>
            </div>
          </div>
          <div class="standing-mobile-stats">
            <div class="standing-mobile-stat">
              <span>Total</span>
              <strong>{format_number(s['total'])}</strong>
            </div>
            <div class="standing-mobile-stat">
              <span>GW</span>
              <strong>{s['gw']}</strong>
            </div>
            <div class="standing-mobile-stat">
              <span>Gap</span>
              <strong>{gap_label}</strong>
            </div>
            <div class="standing-mobile-stat">
              <span>Live Rank</span>
              <strong>{format_rank(s['rank'])}</strong>
            </div>
          </div>
          <span class="{chip_class}">{s['chip']}</span>
        </article>"""

    summary_html = build_summary_html(standings, gw, gw_average)
    trophy_html = build_trophy_cabinet_html().strip()
    archive_html = build_rivalry_archive_html(managers).strip()
    full_html = HTML_TEMPLATE.format(
        gw=gw,
        timestamp=timestamp,
        timestamp_iso=timestamp_iso,
        season=escape(ACTIVE_SEASON),
        movement_icon=ui_icon("movement"),
        trophy_html=trophy_html,
        archive_html=archive_html,
        summary_html=summary_html,
        cards="\n".join(cards),
        standings_html=standings_html,
        standings_mobile_html=standings_mobile_html,
        history_chart_html=history_chart_html
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"\nDashboard updated successfully: {OUTPUT_FILE}")


# ====================== MAIN ======================
if __name__ == "__main__":
    print("Generating Clash of Captains Dashboard...")

    try:
        gw, gw_average, players = get_bootstrap_data()
        managers = get_league_managers()

        print(f"Gameweek: {gw}")

        history_chart_html = generate_history_chart(managers, gw)
        generate_html(gw, gw_average, players, managers, history_chart_html)

    except Exception as e:
        print(f"Error: {e}")

