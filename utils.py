import datetime

import pandas as pd
import streamlit as st
from pybaseball import playerid_lookup, statcast_pitcher


@st.cache_data
def lookup_pitcher(last_name: str, first_name: str) -> pd.DataFrame:
    """Look up a pitcher by name. Returns a DataFrame of matching players."""
    try:
        results = playerid_lookup(last_name.strip(), first_name.strip() if first_name.strip() else None)
        if results.empty:
            # Try fuzzy match
            results = playerid_lookup(last_name.strip(), first_name.strip() if first_name.strip() else None, fuzzy=True)
        return results
    except Exception as e:
        raise RuntimeError(f"Player lookup failed: {e}") from e


@st.cache_data
def fetch_game_data(player_id: int, game_date: str) -> pd.DataFrame:
    """
    Fetch StatCast pitch-level data for a pitcher on a specific date.
    game_date should be 'YYYY-MM-DD'.
    """
    try:
        df = statcast_pitcher(game_date, game_date, player_id=player_id)
        if df is None or df.empty:
            return pd.DataFrame()
        # Ensure game_date column is consistent
        if "game_date" in df.columns:
            df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
        return df.reset_index(drop=True)
    except Exception as e:
        raise RuntimeError(f"StatCast data fetch failed: {e}") from e


@st.cache_data
def fetch_recent_game_dates(player_id: int, n: int = 10) -> list[datetime.date]:
    """Return up to n most recent game dates for a pitcher, within the last 365 days."""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=365)
    try:
        df = statcast_pitcher(str(start), str(end), player_id=player_id)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    dates = pd.to_datetime(df["game_date"]).dt.date.unique()
    return sorted(set(dates), reverse=True)[:n]


def pitch_color_map(pitch_types: list[str]) -> dict:
    """Return a consistent color mapping for pitch types."""
    colors = [
        "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
        "#ff7f00", "#a65628", "#f781bf", "#999999",
    ]
    return {pt: colors[i % len(colors)] for i, pt in enumerate(sorted(set(pitch_types)))}
