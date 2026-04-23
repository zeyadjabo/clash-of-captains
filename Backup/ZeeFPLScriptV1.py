import requests
import json
from datetime import datetime
import os

# CONFIG
MANAGERS = {
    1630460: {"name": "Zee Jabo", "team": "Sesko n Destroy", "yours": True},
    533668:  {"name": "Sam",      "team": "Fergie Time United", "yours": False},
    7617214: {"name": "Joey",     "team": "BAKHAAT", "yours": False}
}

OUTPUT_FILE = "MILF_FPL_dashboard.html"

# DATA FETCHING (unchanged except for clarity)
def get_bootstrap_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        events = data.get('events', [])
        current_gw = next((e['id'] for e in events if e.get('is_current')), None)
        if current_gw is None:
            processed = [e['id'] for e in events if e.get('data_checked') or e.get('finished')]
            current_gw = max(processed) if processed else events[-1]['id']
        
        pos_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        teams = {t['id']: t['short_name'] for t in data.get('teams', [])}
        players = {
            p['id']: {
                'name': p['web_name'],
                'pos': pos_map.get(p.get('element_type'), '?'),
                'team': teams.get(p.get('team'), '?')
            } for p in data.get('elements', [])
        }
        
        print(f"Debug: GW {current_gw} detected")
        return current_gw, players
    
    except Exception as e:
        raise Exception(f"Bootstrap failed: {e}")

def get_manager_summary(entry_id):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/"
    try:
        data = requests.get(url, timeout=8).json()
        return data.get('summary_overall_points', 0), data.get('summary_overall_rank', 'N/A')
    except:
        return 0, 'N/A'

def get_picks(entry_id, gw):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        points = data.get('entry_history', {}).get('points', 0)
        chip = data.get('active_chip') or 'None'
        bench = [p for p in data.get('picks', []) if p.get('position', 0) >= 12]
        auto_subs = data.get('automatic_subs', [])
        full_picks = data.get('picks', [])
        return points, chip, bench, auto_subs, full_picks
    except Exception as e:
        print(f"Picks error {entry_id}: {e}")
        return 0, 'Error', [], [], []

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

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>MILF</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); color: #e0e0e0; margin:0; padding:20px; min-height:100vh; }}
    h1 {{ text-align:center; color:#ffd700; text-shadow:0 0 10px rgba(255,215,0,0.6); margin-bottom:6px; }}
    .league-name {{ text-align:center; color:#aaa; font-size:0.9em; margin-bottom:20px; }}
    .gw-highlight {{ text-align:center; font-size:1.8em; font-weight:bold; color:#ffd700; margin-bottom:4px; background:rgba(255,215,0,0.1); padding:12px; border-radius:8px; border:1px solid #ffd700; }}
    .update-time {{ text-align:center; color:#888; font-size:0.85em; margin-bottom:20px; }}
    .container {{ max-width:1200px; margin:0 auto; display:grid; grid-template-columns:repeat(auto-fit, minmax(380px,1fr)); gap:25px; }}
    .card {{ background:rgba(255,255,255,0.08); border-radius:12px; padding:20px; backdrop-filter:blur(10px); border:1px solid rgba(255,255,255,0.15); box-shadow:0 8px 32px rgba(0,0,0,0.4); transition:transform 0.2s; }}
    .card:hover {{ transform:translateY(-5px); }}
    .card.yours {{ border-color:#ffd700; box-shadow:0 0 25px rgba(255,215,0,0.4); }}
    .card h2 {{ margin:0 0 12px; color:#ffd700; font-size:1.5em; }}
    .card h3 {{ color:#4fc3f7; margin:20px 0 8px; font-size:1.2em; }}
    table {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:0.95em; }}
    th,td {{ padding:8px 10px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.1); }}
    th {{ color:#4fc3f7; }}
    .no-data {{ color:#888; font-style:italic; }}
    .divider {{ border-top:1px solid rgba(255,255,255,0.15); margin:15px 0; }}
    .refresh-btn {{ display:block; margin:20px auto; padding:10px 24px; background:#ffd700; color:#0f2027; border:none; border-radius:6px; cursor:pointer; font-weight:bold; font-size:1em; }}
    .refresh-btn:hover {{ background:#ffeb3b; }}
    .cap-vice {{ margin:10px 0; font-size:0.95em; }}
    .cap {{ color:#ff5722; font-weight:bold; }}
    .vice {{ color:#4caf50; font-weight:bold; }}
    .transfer-out {{ color:#f44336; }}
    .transfer-in {{ color:#4caf50; }}
    .chip-highlight {{ padding:12px; margin:12px 0; border-radius:8px; text-align:center; font-weight:bold; font-size:1.1em; }}
    .chip-none {{ background:rgba(100,100,100,0.4); border:1px solid #666; }}
    .chip-tc {{ background:rgba(255,215,0,0.25); border:2px solid #ffd700; color:#ffeb3b; }}
    .chip-bb {{ background:rgba(76,175,80,0.25); border:2px solid #4caf50; color:#c8e6c9; }}
    .chip-fh {{ background:rgba(33,150,243,0.25); border:2px solid #2196f3; color:#bbdefb; }}
    .chip-wc {{ background:rgba(156,39,176,0.25); border:2px solid #9c27b0; color:#e1bee7; }}
  </style>
  <script>
    function refreshPage() {{ location.reload(); }}
  </script>
</head>
<body>
  <h1>MILF Dashboard</h1>
  <div class="gw-highlight">Gameweek {gw}</div>
  <div class="league-name">MILF League</div>
  <div class="update-time">Last updated: {timestamp}</div>
  <button class="refresh-btn" onclick="refreshPage()">Refresh Dashboard</button>
  <div class="container">{cards}</div>
</body>
</html>"""

CARD_TEMPLATE = """
<div class="card {yours_class}">
  <h2>{team} <small>({manager})</small></h2>
  
  <div class="chip-highlight {chip_class}">{chip_display}</div>
  
  <div class="section">
    <strong>Total Points:</strong> {total_points}<br>
    <strong>Live Rank:</strong> {live_rank}<br>
    <strong>GW {gw} Points:</strong> {points}
  </div>
  <div class="divider"></div>
  
  <h3>Captain & Vice</h3>
  {cap_vice_html}
  
  {bench_section}
  
  <h3>Automatic Subs</h3>{autosubs_html}
  <h3>Transfers this GW</h3>{transfers_html}
</div>
"""

def generate_html(gw, players):
    cards = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M EST")
    
    for mid, info in MANAGERS.items():
        total_points, live_rank = get_manager_summary(mid)
        points, chip, bench_raw, auto_subs, full_picks = get_picks(mid, gw)
        transfers = get_transfers(mid, gw)
        
        # Chip highlight
        chip_display = "No chip active this GW"
        chip_class = "chip-none"
        if chip and chip != 'None':
            chip_name = chip.replace('_', ' ').title()
            if 'triple' in chip.lower() or chip == '3xc':
                tc_player = next((players.get(p['element'], {}).get('name', 'Unknown') 
                                for p in full_picks if p.get('multiplier') == 3), None)
                chip_display = f"<strong>TRIPLE CAPTAIN ACTIVE!</strong><br>On: {tc_player or 'Processing...'}"
                chip_class = "chip-tc"
            elif 'bench' in chip.lower():
                chip_display = f"<strong>BENCH BOOST ACTIVE</strong><br>All bench players scoring"
                chip_class = "chip-bb"
            elif 'freehit' in chip.lower():
                chip_display = f"<strong>FREE HIT ACTIVE</strong><br>Unlimited transfers"
                chip_class = "chip-fh"
            elif 'wildcard' in chip.lower():
                chip_display = f"<strong>WILDCARD ACTIVE</strong><br>Unlimited free transfers"
                chip_class = "chip-wc"
            else:
                chip_display = f"<strong>{chip_name} ACTIVE</strong>"
        
        # Captain & Vice
        captain = next((players.get(p['element'], {}).get('name', 'N/A') for p in full_picks if p.get('is_captain')), 'N/A')
        vice = next((players.get(p['element'], {}).get('name', 'N/A') for p in full_picks if p.get('is_vice_captain')), 'N/A')
        cap_vice_html = f'<p class="cap-vice"><span class="cap">Captain:</span> {captain}<br><span class="vice">Vice:</span> {vice}</p>'
        
        # Bench: only show if any bench player is active (multiplier == 1)
        active_bench = [p for p in bench_raw if p.get('multiplier') == 1]
        bench_section = ""
        if active_bench:
            bench_rows = []
            for p in bench_raw:
                player = players.get(p['element'], {'name':'Unknown', 'pos':'?', 'team':'?'})
                status = "Active (subbed in)" if p.get('multiplier') == 1 else "Unused"
                bench_rows.append(f"<tr><td>{player['name']}</td><td>{player['pos']}</td><td>{player['team']}</td><td>{status}</td></tr>")
            bench_section = f"""
            <h3>Bench (Utilized)</h3>
            <table><tr><th>Player</th><th>Pos</th><th>Team</th><th>Status</th></tr>{''.join(bench_rows)}</table>
            <div class="divider"></div>
            """
        
        # Auto subs
        autosubs_html = '<ul>' + ''.join(f"<li>In: {players.get(s['element_in'], {'name':'?'})['name']} • Out: {players.get(s['element_out'], {'name':'?'})['name']}</li>" for s in auto_subs) + '</ul>' if auto_subs else '<p class="no-data">No auto subs this GW</p>'
        
        # Transfers with arrows
        trans_lines = []
        for t in transfers:
            in_p = players.get(t.get('element_in'), {'name':'?'})
            out_p = players.get(t.get('element_out'), {'name':'?'})
            price_in = t.get('purchase_price', 0) / 10
            price_out = t.get('selling_price', 0) / 10
            trans_lines.append(f"<li><span class='transfer-out'>{out_p['name']}</span> ↔ <span class='transfer-in'>{in_p['name']}</span><br>£{price_out:.1f} → £{price_in:.1f} <small>({t.get('time','N/A')})</small></li>")
        transfers_html = '<ul>' + ''.join(trans_lines) + '</ul>' if trans_lines else '<p class="no-data">No transfers this GW</p>'
        
        card_html = CARD_TEMPLATE.format(
            yours_class="yours" if info['yours'] else "",
            team=info['team'], manager=info['name'], gw=gw, points=points,
            total_points=total_points, live_rank=live_rank,
            chip_display=chip_display, chip_class=chip_class,
            cap_vice_html=cap_vice_html,
            bench_section=bench_section,
            autosubs_html=autosubs_html,
            transfers_html=transfers_html
        )
        cards.append(card_html)
    
    full_html = HTML_TEMPLATE.format(timestamp=timestamp, gw=gw, cards='\n'.join(cards))
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    abs_path = os.path.abspath(OUTPUT_FILE)
    print(f"\nDashboard saved to: {abs_path}")
    print("Start local server:")
    print("  python -m http.server 8000")
    print(f"Then visit: http://127.0.0.1:8000/{OUTPUT_FILE}")

# MAIN
if __name__ == "__main__":
    print("Generating MILF FPL Dashboard...")
    try:
        gw, players = get_bootstrap_data()
        print(f"→ Detected Gameweek: {gw}")
        generate_html(gw, players)
    except Exception as e:
        print(f"Error: {e}")
        print("Tip: Check debug messages. Try hardcoding gw = 25 if GW is processing.")