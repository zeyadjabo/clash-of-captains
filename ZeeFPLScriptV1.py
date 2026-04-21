import requests
from datetime import datetime
import os

# CONFIG
MANAGERS = {
    1630460: {"name": "Zee", "team": "Sesko n Destroy", "yours": True},
    533668:  {"name": "Sam",      "team": "Fergie Time United", "yours": False},
    7617214: {"name": "Joey",     "team": "BAKHAAT", "yours": False}
}

OUTPUT_FILE = "index.html"

# ====================== DATA FETCHING ======================
def get_bootstrap_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    try:
        data = requests.get(url, timeout=10).json()
        events = data.get('events', [])
        current_gw = next((e['id'] for e in events if e.get('is_current')), None)
        if current_gw is None:
            processed = [e['id'] for e in events if e.get('data_checked') or e.get('finished')]
            current_gw = max(processed) if processed else events[-1]['id']
        
        # Player lookup dictionary
        players = {p['id']: p['web_name'] for p in data.get('elements', [])}
        
        print(f"Debug: GW {current_gw} detected")
        return current_gw, players
    except Exception as e:
        raise Exception(f"Bootstrap failed: {e}")

def get_manager_summary(entry_id):
    try:
        data = requests.get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/", timeout=8).json()
        return data.get('summary_overall_points', 0), data.get('summary_overall_rank', 'N/A')
    except:
        return 0, 'N/A'

def get_picks(entry_id, gw):
    try:
        data = requests.get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/", timeout=8).json()
        points = data.get('entry_history', {}).get('points', 0)
        chip = data.get('active_chip') or 'None'
        return points, chip
    except:
        return 0, 'None'

def get_transfers(entry_id, gw):
    urls = [
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers-latest/",
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/"
    ]
    for url in urls:
        try:
            data = requests.get(url, timeout=8).json()
            if isinstance(data, list):
                if 'transfers-latest' in url and data:
                    return data
                return [t for t in data if t.get('event') == gw]
        except:
            pass
    return []

# ====================== HTML TEMPLATE ======================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>MILF LEAGUE // GROK PROTOCOL</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Exo+2:wght@400;600;700&display=swap');

    :root {{
      --neon-gold: #ffd700;
      --neon-cyan: #00f5ff;
      --neon-pink: #ff00c8;
      --dark-bg: #05080f;
    }}

    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      font-family: 'Exo 2', sans-serif;
      background: var(--dark-bg);
      color: #e0f0ff;
      min-height: 100vh;
      position: relative;
    }}

    body::before, body::after {{
      content: ''; position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -2;
    }}
    body::before {{
      background: radial-gradient(circle at 30% 20%, rgba(255,215,0,0.12), transparent 50%),
                  radial-gradient(circle at 70% 80%, rgba(255,0,200,0.12), transparent 50%);
      animation: bgPulse 25s infinite alternate;
    }}
    @keyframes bgPulse {{ 0% {{ opacity: 0.6; }} 100% {{ opacity: 1; }} }}

    body::after {{
      background: linear-gradient(rgba(0,245,255,0.03) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(0,245,255,0.03) 1px, transparent 1px);
      background-size: 60px 60px;
      animation: gridMove 60s linear infinite;
      z-index: -1;
    }}
    @keyframes gridMove {{ 0% {{ background-position: 0 0; }} 100% {{ background-position: 120px 120px; }} }}

    h1 {{
      text-align: center;
      font-family: 'Orbitron', sans-serif;
      font-size: clamp(2.8rem, 9vw, 5.2rem);
      font-weight: 900;
      letter-spacing: 8px;
      background: linear-gradient(90deg, #ffd700, #ff00c8, #00f5ff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin: 20px 0 8px;
      text-shadow: 0 0 40px rgba(255,215,0,0.8);
    }}

    .subtitle {{ text-align:center; color:#ff00c8; font-size:1.2rem; letter-spacing:6px; margin-bottom:15px; }}

    .gw-highlight {{
      text-align:center; font-size: clamp(2rem, 7vw, 3.5rem); font-weight:900;
      background:rgba(5,8,15,0.95); border:4px solid var(--neon-gold); color:var(--neon-gold);
      padding:20px; border-radius:20px; margin:15px auto; max-width:720px;
      box-shadow:0 0 70px rgba(255,215,0,0.8);
    }}

    /* LEAGUE TABLE - Centered & Improved */
    .league-table {{
      max-width: 1100px;
      margin: 30px auto;
      background: rgba(15,22,45,0.95);
      border-radius: 20px;
      overflow: hidden;
      border: 3px solid var(--neon-gold);
      box-shadow: 0 0 60px rgba(255,215,0,0.5);
    }}
    .league-table table {{ 
      width:100%; 
      border-collapse:collapse; 
    }}
    .league-table th {{
      background: rgba(255,215,0,0.2);
      color: var(--neon-gold);
      padding: 16px 12px;
      font-size: 1.1rem;
    }}
    .league-table td {{
      padding: 16px 12px;
      text-align: center;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }}
    .league-table tr.yours {{
      background: rgba(255,215,0,0.15) !important;
      font-weight: bold;
    }}

    .container {{
      max-width:1400px;
      margin:40px auto;
      display:grid;
      grid-template-columns:repeat(auto-fit, minmax(420px,1fr));
      gap:28px;
      padding:0 15px;
    }}

    .card {{
      background:linear-gradient(145deg, rgba(15,22,45,0.96), rgba(8,12,28,0.98));
      border-radius:24px;
      padding:26px;
      border:2px solid rgba(255,215,0,0.3);
    }}
    .card.yours {{ border-color:var(--neon-gold); box-shadow:0 0 60px rgba(255,215,0,0.6); }}

    .transfer-list {{
      list-style: none;
      padding: 0;
    }}
    .transfer-list li {{
      background: rgba(0,0,0,0.45);
      padding: 14px 16px;
      margin: 10px 0;
      border-radius: 12px;
      border-left: 5px solid #ff2d55;
    }}
    .transfer-list small {{ color: #888; font-size: 0.9rem; }}

    .refresh-btn {{
      display:block; margin:35px auto; padding:18px 55px; font-size:1.25rem; font-weight:900;
      background:linear-gradient(45deg,#ffd700,#ffea00); color:#05080f; border:none;
      border-radius:50px; cursor:pointer; box-shadow:0 0 50px rgba(255,215,0,0.8);
    }}
    .refresh-btn:hover {{ transform:scale(1.08); }}

    @media (max-width: 768px) {{
      .container {{ grid-template-columns:1fr; }}
      .league-table th, .league-table td {{ padding: 12px 8px; }}
    }}
  </style>
</head>
<body>
  <h1>MILF PROTOCOL</h1>
  <div class="subtitle">Abu Alzooz, The #1 in Clash of Captains // MI-to-CAL TRANSMISSION</div>
  <div class="gw-highlight">GAMEWEEK {gw}</div>
  <div class="update-time">Last scanned: {timestamp} EST</div>

  <div class="league-table">
    <table>
      <thead>
        <tr>
          <th>Pos</th>
          <th>Team</th>
          <th>Manager</th>
          <th>Total</th>
          <th>GW Points</th>
          <th>Live Rank</th>
          <th>Chip</th>
        </tr>
      </thead>
      <tbody>{standings_html}</tbody>
    </table>
  </div>

  <button class="refresh-btn" onclick="location.reload()">
    <i class="fas fa-satellite-dish"></i> TRANSMIT FRESH INTEL
  </button>

  <div class="container">{cards}</div>
</body>
</html>"""

# CARD TEMPLATE (Simplified + Transfers)
CARD_TEMPLATE = """
<div class="card {yours_class}">
  <h2 style="font-family:Orbitron; letter-spacing:2px; margin-bottom:20px;">{team} <small style="color:#888;">({manager})</small></h2>
  
  <h3 style="color:#00f5ff; margin:20px 0 12px;">TRANSFERS THIS GW</h3>
  {transfers_html}
</div>
"""

def generate_html(gw, players):
    cards = []
    standings = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M EST")
    
    for mid, info in MANAGERS.items():
        total_points, live_rank = get_manager_summary(mid)
        points, chip = get_picks(mid, gw)
        transfers = get_transfers(mid, gw)
        
        # Clean Transfers with proper name lookup
        trans_lines = []
        for t in transfers:
            in_id = t.get('element_in')
            out_id = t.get('element_out')
            in_name = players.get(in_id, 'Unknown')
            out_name = players.get(out_id, 'Unknown')
            
            raw_time = t.get('time', '')
            clean_time = raw_time[:16].replace('T', ' ') if raw_time else 'N/A'
            
            trans_lines.append(
                f"<li><span class='transfer-out'>{out_name}</span> ↔ <span class='transfer-in'>{in_name}</span><br>"
                f"<small>£0.0 → £0.0 • {clean_time}</small></li>"
            )
        
        transfers_html = '<ul class="transfer-list">' + ''.join(trans_lines) + '</ul>' if trans_lines else '<p style="color:#888;">No transfers this GW</p>'
        
        cards.append(CARD_TEMPLATE.format(
            yours_class="yours" if info['yours'] else "",
            team=info['team'], 
            manager=info['name'],
            transfers_html=transfers_html
        ))
        
        # Emojis for each team
        emojis = {
            "Sesko n Destroy": "🔥🥇",
            "Fergie Time United": "🇪🇬👑🥈",
            "BAKHAAT": "🏳️‍🌈"
        }
        
        team_emoji = emojis.get(info['team'], "⚽")
        
        # ... inside the standings list:
        standings.append({
            'team': info['team'],
            'emoji': team_emoji,
            'manager': info['name'],
            'total': total_points,
            'gw': points,
            'rank': live_rank,
            'chip': 'WILDCARD' if 'wildcard' in str(chip).lower() else 'None',
            'yours': info['yours']
        })
    
    # Standings
    standings.sort(key=lambda x: x['total'], reverse=True)
    standings_html = ""
    for i, s in enumerate(standings, 1):
        row_class = ' class="yours"' if s['yours'] else ''
        # Format rank with commas
        try:
            formatted_rank = f"#{int(s['rank']):,}"
        except:
            formatted_rank = f"#{s['rank']}"
  
        standings_html += f"""
        <tr{row_class}>
          <td><strong>#{i}</strong></td>
          <td>{s['emoji']} {s['team']}</td>
          <td>{s['manager']}</td>
          <td><strong>{s['total']}</strong></td>
          <td>{s['gw']}</td>
          <td>{formatted_rank}</td>
          <td>{s['chip']}</td>
        </tr>"""
    
    full_html = HTML_TEMPLATE.format(gw=gw, timestamp=timestamp, cards='\n'.join(cards), standings_html=standings_html)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"\n✅ Dashboard updated successfully → {OUTPUT_FILE}")

# MAIN
if __name__ == "__main__":
    print("Generating MILF FPL Dashboard...")
    try:
        gw, players = get_bootstrap_data()   # ← changed here
        print(f"→ Gameweek: {gw}")
        generate_html(gw, players)           # ← pass players
    except Exception as e:
        print(f"Error: {e}")