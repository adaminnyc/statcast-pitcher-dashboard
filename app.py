import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import fetch_game_data, lookup_pitcher, pitch_color_map

st.set_page_config(page_title="StatCast Pitcher Dashboard", layout="wide")
st.title("StatCast Pitcher Performance")

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pitcher Lookup")
    first_name = st.text_input("First Name", placeholder="e.g. Gerrit")
    last_name = st.text_input("Last Name", placeholder="e.g. Cole")
    game_date = st.date_input(
        "Game Date",
        value=datetime.date(2024, 9, 1),
        min_value=datetime.date(2008, 1, 1),
        max_value=datetime.date.today(),
    )
    load_btn = st.button("Load Data", type="primary", use_container_width=True)

# ── State management ──────────────────────────────────────────────────────────
if "pitcher_candidates" not in st.session_state:
    st.session_state.pitcher_candidates = None
if "selected_player_id" not in st.session_state:
    st.session_state.selected_player_id = None
if "pitch_data" not in st.session_state:
    st.session_state.pitch_data = None

if load_btn:
    if not last_name.strip():
        st.sidebar.error("Please enter at least a last name.")
    else:
        with st.sidebar:
            with st.spinner("Looking up pitcher..."):
                try:
                    candidates = lookup_pitcher(last_name, first_name)
                    st.session_state.pitcher_candidates = candidates
                    st.session_state.selected_player_id = None
                    st.session_state.pitch_data = None
                except RuntimeError as e:
                    st.error(str(e))

# ── Pitcher selection (if multiple matches) ───────────────────────────────────
if st.session_state.pitcher_candidates is not None:
    candidates = st.session_state.pitcher_candidates
    if candidates.empty:
        st.warning("No pitcher found with that name. Try fuzzy spelling or check the name.")
    else:
        # Build display labels
        def make_label(row):
            first = row.get("name_first", "")
            last = row.get("name_last", "")
            first_year = int(row["mlb_played_first"]) if pd.notna(row.get("mlb_played_first")) else "?"
            last_year = int(row["mlb_played_last"]) if pd.notna(row.get("mlb_played_last")) else "?"
            return f"{first} {last} ({first_year}–{last_year})"

        labels = candidates.apply(make_label, axis=1).tolist()
        mlbam_ids = candidates["key_mlbam"].tolist()

        if len(labels) == 1:
            selected_label = labels[0]
            selected_id = mlbam_ids[0]
        else:
            with st.sidebar:
                selected_label = st.selectbox("Multiple matches — select pitcher:", labels)
            selected_id = mlbam_ids[labels.index(selected_label)]

        if st.session_state.selected_player_id != selected_id:
            st.session_state.selected_player_id = selected_id
            st.session_state.pitch_data = None

        # Fetch pitch data
        if st.session_state.pitch_data is None:
            with st.spinner(f"Fetching StatCast data for {selected_label} on {game_date}..."):
                try:
                    df = fetch_game_data(int(selected_id), str(game_date))
                    st.session_state.pitch_data = df
                except RuntimeError as e:
                    st.error(str(e))

# ── Charts ────────────────────────────────────────────────────────────────────
df: pd.DataFrame | None = st.session_state.pitch_data

if df is not None:
    if df.empty:
        st.warning("No StatCast data found for this pitcher on that date. They may not have started or the date is outside the StatCast era (2008+).")
    else:
        pitcher_name = (
            f"{df['player_name'].iloc[0]}" if "player_name" in df.columns else "Pitcher"
        )
        st.subheader(f"{pitcher_name} — {game_date}")

        # Summary metrics
        pitch_types = df["pitch_type"].dropna()
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Pitches", len(df))
        col2.metric("Pitch Types", pitch_types.nunique())
        avg_velo = df["release_speed"].mean()
        col3.metric("Avg Velocity", f"{avg_velo:.1f} mph" if pd.notna(avg_velo) else "N/A")

        # Pitch type breakdown table
        with st.expander("Pitch Type Breakdown"):
            breakdown = (
                df.groupby("pitch_name")
                .agg(
                    Count=("pitch_type", "count"),
                    Avg_Velo=("release_speed", "mean"),
                    Avg_Spin=("release_spin_rate", "mean"),
                )
                .rename(columns={"Avg_Velo": "Avg Velo (mph)", "Avg_Spin": "Avg Spin (RPM)"})
                .round(1)
                .sort_values("Count", ascending=False)
            )
            st.dataframe(breakdown)

        colors = pitch_color_map(df["pitch_type"].dropna().unique().tolist())

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Strike Zone", "Pitch Movement", "Velocity", "Pitch Sequence"]
        )

        # ── Tab 1: Pitch Location ──────────────────────────────────────────
        with tab1:
            st.markdown("**Pitch location at home plate (catcher's view)**")
            loc_df = df.dropna(subset=["plate_x", "plate_z"])
            if loc_df.empty:
                st.info("No plate location data available.")
            else:
                fig = px.scatter(
                    loc_df,
                    x="plate_x",
                    y="plate_z",
                    color="pitch_name",
                    hover_data={"release_speed": True, "description": True, "plate_x": False, "plate_z": False},
                    labels={"plate_x": "Horizontal (ft)", "plate_z": "Vertical (ft)", "pitch_name": "Pitch"},
                    title="Pitch Locations",
                )
                # Draw strike zone
                fig.add_shape(
                    type="rect",
                    x0=-0.83, x1=0.83,
                    y0=1.5, y1=3.5,
                    line=dict(color="black", width=2),
                    fillcolor="rgba(0,0,0,0)",
                )
                fig.update_layout(xaxis=dict(range=[-2.5, 2.5]), yaxis=dict(range=[0, 5]))
                st.plotly_chart(fig, use_container_width=True)

        # ── Tab 2: Pitch Movement ──────────────────────────────────────────
        with tab2:
            st.markdown("**Horizontal vs vertical break (inches from expected straight path)**")
            move_df = df.dropna(subset=["pfx_x", "pfx_z"])
            # pfx values are in feet; convert to inches
            move_df = move_df.copy()
            move_df["pfx_x_in"] = move_df["pfx_x"] * 12
            move_df["pfx_z_in"] = move_df["pfx_z"] * 12
            if move_df.empty:
                st.info("No movement data available.")
            else:
                fig = px.scatter(
                    move_df,
                    x="pfx_x_in",
                    y="pfx_z_in",
                    color="pitch_name",
                    hover_data={"release_spin_rate": True, "release_speed": True, "pfx_x_in": False, "pfx_z_in": False},
                    labels={"pfx_x_in": "Horizontal Break (in)", "pfx_z_in": "Vertical Break (in)", "pitch_name": "Pitch"},
                    title="Pitch Movement Profile",
                )
                # Add crosshairs at origin
                fig.add_hline(y=0, line_dash="dot", line_color="gray")
                fig.add_vline(x=0, line_dash="dot", line_color="gray")
                st.plotly_chart(fig, use_container_width=True)

        # ── Tab 3: Velocity by Pitch Type ──────────────────────────────────
        with tab3:
            st.markdown("**Velocity distribution per pitch type**")
            velo_df = df.dropna(subset=["release_speed", "pitch_name"])
            if velo_df.empty:
                st.info("No velocity data available.")
            else:
                fig = px.violin(
                    velo_df,
                    x="pitch_name",
                    y="release_speed",
                    color="pitch_name",
                    box=True,
                    points="all",
                    labels={"pitch_name": "Pitch Type", "release_speed": "Velocity (mph)"},
                    title="Velocity by Pitch Type",
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        # ── Tab 4: Pitch Sequence ──────────────────────────────────────────
        with tab4:
            st.markdown("**Velocity over the course of the game, colored by pitch type**")
            seq_df = df.dropna(subset=["release_speed", "pitch_name"]).copy()
            seq_df["pitch_number"] = range(1, len(seq_df) + 1)
            if seq_df.empty:
                st.info("No sequence data available.")
            else:
                fig = px.scatter(
                    seq_df,
                    x="pitch_number",
                    y="release_speed",
                    color="pitch_name",
                    symbol="description",
                    hover_data={"inning": True, "balls": True, "strikes": True, "description": True, "pitch_number": False},
                    labels={"pitch_number": "Pitch #", "release_speed": "Velocity (mph)", "pitch_name": "Pitch"},
                    title="Pitch Sequence",
                )
                # Add a trend line per pitch type using a smoothed line
                for pname, group in seq_df.groupby("pitch_name"):
                    if len(group) >= 3:
                        fig.add_trace(
                            go.Scatter(
                                x=group["pitch_number"],
                                y=group["release_speed"].rolling(3, min_periods=1).mean(),
                                mode="lines",
                                line=dict(width=1, dash="dot"),
                                showlegend=False,
                                name=f"{pname} trend",
                            )
                        )
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Enter a pitcher name and game date in the sidebar, then click **Load Data**.")
