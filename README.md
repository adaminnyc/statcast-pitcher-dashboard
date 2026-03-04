# StatCast Pitcher Dashboard

A Streamlit web app for exploring MLB pitcher performance using pitch-level StatCast data from Baseball Savant. Look up any pitcher by name, pick a game date, and get interactive charts showing how they pitched that day.

## What It Shows

- **Strike Zone** — where each pitch crossed the plate (catcher's view), colored by pitch type
- **Pitch Movement** — horizontal vs. vertical break for each pitch type
- **Velocity** — speed distribution per pitch type as a violin plot
- **Pitch Sequence** — velocity over the course of the game with dotted trend lines, showing how stuff changed inning by inning

Data is available for any game from 2008 to the present.

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/adaminnyc/statcast-pitcher-dashboard.git
cd statcast-pitcher-dashboard
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

## Running the App

```bash
source .venv/bin/activate
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

## Usage

1. Enter a pitcher's first and last name in the sidebar
2. Click **Load Data**
3. If multiple players share the name, choose the correct one from the dropdown
4. The app automatically loads the pitcher's **last 10 game dates** as a dropdown — select one to view that game
5. To look up an older game, choose **"Enter a specific date..."** at the bottom of the dropdown and pick any date back to 2008

> **Tip:** Try Gerrit Cole to see his recent starts auto-populated.
