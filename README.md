# ⚽ Clash of Captains: FPL Dashboard

A high-performance, neon-themed Fantasy Premier League (FPL) dashboard for tracking the "Clash of Captains" mini-league rivalry between **Zee, Sam, and Joey**.

## 🔗 Live Dashboard
**[View the Live Stats Here](https://zeyadjabo.github.io/clash-of-captains/)**

## 🚀 Features
* **Live Standings:** Real-time total points and overall rank tracking.
* **Chip Detection:** Automatically identifies and displays active chips (Wildcard, Free Hit, etc.).
* **Transfer Tracking:** Monitor every move made by league rivals during the current Gameweek.
* **Historical Rank Chart:** Plotly-powered overall rank progress chart with mobile-friendly sizing.
* **Blank Gameweek Insights:** Custom manual insights for strategic planning (e.g., GW34 Blank).
* **Automated Updates:** GitHub Actions refreshes the generated dashboard twice daily and supports manual runs.

## 🛠️ Technical Setup
The dashboard is powered by a Python engine that interacts with the official FPL API and generates a static, responsive HTML5/CSS3 interface.

### Prerequisites
* Python 3.x
* Python dependencies listed in `requirements.txt`:
  * `requests`
  * `plotly`

### Installation
1. Clone the repository:
   git clone [https://github.com/zeyadjabo/clash-of-captains.git](https://github.com/zeyadjabo/clash-of-captains.git)

2. Install dependencies:
   pip install -r requirements.txt

3. Run the update script:
   python dashboard_engine.py

## ⚙️ Automated Workflow
The `.github/workflows/update-dashboard.yml` workflow installs dependencies from `requirements.txt`, runs `dashboard_engine.py`, and commits any generated `index.html` changes back to the repository.

Scheduled runs are configured for 9 AM and 9 PM Eastern, with manual runs available from the GitHub Actions tab.
