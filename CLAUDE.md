# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
source .venv/bin/activate
streamlit run app.py
```

Or without activating the venv:
```bash
.venv/bin/streamlit run app.py
```

## Architecture

Two-file structure:

- **`utils.py`** — Data layer. Contains `lookup_pitcher()` and `fetch_game_data()`, both decorated with `@st.cache_data` to avoid redundant API calls across Streamlit reruns. `pitch_color_map()` produces a stable color assignment for pitch types.
- **`app.py`** — UI layer. Pure Streamlit: sidebar inputs → session state → charts. No business logic lives here.

### Data Flow

1. User enters pitcher name + date → clicks "Load Data"
2. `lookup_pitcher()` calls `pybaseball.playerid_lookup()` to resolve the name to an MLBAM player ID (falls back to fuzzy matching if exact match returns nothing)
3. If multiple candidates, a selectbox appears in the sidebar
4. `fetch_game_data(player_id, game_date)` calls `pybaseball.statcast_pitcher()` for that single date
5. The resulting pitch-level DataFrame drives all four chart tabs

### Key StatCast Fields

| Field | Chart |
|---|---|
| `plate_x`, `plate_z` | Strike Zone (feet from center) |
| `pfx_x`, `pfx_z` | Pitch Movement (feet → converted to inches in app.py) |
| `release_speed` | Velocity + Pitch Sequence |
| `release_spin_rate` | Shown in Movement hover |
| `pitch_type`, `pitch_name` | Color coding across all charts |
| `description` | Symbol encoding in Pitch Sequence |

### Session State Keys

- `pitcher_candidates` — DataFrame from `lookup_pitcher()`
- `selected_player_id` — MLBAM int ID of chosen pitcher
- `pitch_data` — pitch-level DataFrame for the selected game

StatCast data is available from 2008 onward; launch angle and some advanced fields only from 2015.
