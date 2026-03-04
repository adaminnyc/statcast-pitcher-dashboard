import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import fetch_game_data, fetch_recent_game_dates, lookup_pitcher, pitch_color_map

st.set_page_config(page_title="StatCast Pitcher Dashboard", layout="wide")
st.title("StatCast Pitcher Performance")

CUSTOM_DATE_OPTION = "Enter a specific date..."

# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Pitcher Lookup")
    first_name = st.text_input("First Name", placeholder="e.g. Gerrit")
    last_name = st.text_input("Last Name", placeholder="e.g. Cole")
    load_btn = st.button("Load Data", type="primary", use_container_width=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key in ("pitcher_candidates", "selected_player_id", "recent_game_dates", "selected_date", "pitch_data"):
    if key not in st.session_state:
        st.session_state[key] = None

# ── Step 1: Pitcher name lookup ───────────────────────────────────────────────
if load_btn:
    if not last_name.strip():
        st.sidebar.error("Please enter at least a last name.")
    else:
        with st.sidebar, st.spinner("Looking up pitcher..."):
            try:
                candidates = lookup_pitcher(last_name, first_name)
                st.session_state.pitcher_candidates = candidates
                st.session_state.selected_player_id = None
                st.session_state.recent_game_dates = None
                st.session_state.selected_date = None
                st.session_state.pitch_data = None
            except RuntimeError as e:
                st.sidebar.error(str(e))

# ── Step 2: Resolve pitcher ID (handle multiple matches) ──────────────────────
if st.session_state.pitcher_candidates is not None:
    candidates = st.session_state.pitcher_candidates
    if candidates.empty:
        st.warning("No pitcher found with that name. Try a different spelling.")
    else:
        def make_label(row):
            first = row.get("name_first", "")
            last = row.get("name_last", "")
            def safe_year(val):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return "?"
            first_year = safe_year(row.get("mlb_played_first"))
            last_year = safe_year(row.get("mlb_played_last"))
            return f"{first} {last} ({first_year}–{last_year})"

        labels = candidates.apply(make_label, axis=1).tolist()
        mlbam_ids = candidates["key_mlbam"].tolist()

        if len(labels) == 1:
            selected_id = mlbam_ids[0]
        else:
            with st.sidebar:
                selected_label = st.selectbox("Multiple matches — select pitcher:", labels)
            selected_id = mlbam_ids[labels.index(selected_label)]

        # When the player ID changes, clear downstream state
        if st.session_state.selected_player_id != selected_id:
            st.session_state.selected_player_id = selected_id
            st.session_state.recent_game_dates = None
            st.session_state.selected_date = None
            st.session_state.pitch_data = None

        # ── Step 3: Fetch recent game dates ───────────────────────────────
        if st.session_state.recent_game_dates is None:
            with st.sidebar, st.spinner("Finding recent starts..."):
                dates = fetch_recent_game_dates(int(selected_id))
                st.session_state.recent_game_dates = dates

        recent_dates: list[datetime.date] = st.session_state.recent_game_dates

        # ── Step 4: Date selector ─────────────────────────────────────────
        with st.sidebar:
            st.markdown("**Game Date**")
            if recent_dates:
                date_options = [d.strftime("%Y-%m-%d  (%a, %b %d %Y)") for d in recent_dates]
                date_options.append(CUSTOM_DATE_OPTION)
                chosen_label = st.selectbox("Recent starts (last 10):", date_options)
            else:
                st.info("No recent starts found in the last 365 days. Enter a date manually.")
                chosen_label = CUSTOM_DATE_OPTION

            if chosen_label == CUSTOM_DATE_OPTION:
                manual_date = st.date_input(
                    "Specific date:",
                    value=datetime.date(2024, 9, 1),
                    min_value=datetime.date(2008, 1, 1),
                    max_value=datetime.date.today(),
                )
                resolved_date = manual_date
            else:
                # Parse date from label (first 10 chars are YYYY-MM-DD)
                resolved_date = datetime.date.fromisoformat(chosen_label[:10])

        # When date changes, clear pitch data
        if st.session_state.selected_date != resolved_date:
            st.session_state.selected_date = resolved_date
            st.session_state.pitch_data = None

        # ── Step 5: Fetch pitch data ──────────────────────────────────────
        if st.session_state.pitch_data is None:
            with st.spinner(f"Fetching StatCast data for {resolved_date}..."):
                try:
                    df = fetch_game_data(int(selected_id), str(resolved_date))
                    st.session_state.pitch_data = df
                except RuntimeError as e:
                    st.error(str(e))

# ── Charts ────────────────────────────────────────────────────────────────────
df: pd.DataFrame | None = st.session_state.pitch_data

if df is not None:
    if df.empty:
        st.warning("No StatCast data found for this pitcher on that date. They may not have started or the date is outside the StatCast era (2008+).")
    else:
        pitcher_name = df["player_name"].iloc[0] if "player_name" in df.columns else "Pitcher"
        st.subheader(f"{pitcher_name} — {st.session_state.selected_date}")

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Pitches", len(df))
        col2.metric("Pitch Types", df["pitch_type"].dropna().nunique())
        avg_velo = df["release_speed"].mean()
        col3.metric("Avg Velocity", f"{avg_velo:.1f} mph" if pd.notna(avg_velo) else "N/A")

        with st.expander("Pitch Type Breakdown"):
            breakdown = (
                df.groupby("pitch_name")
                .agg(Count=("pitch_type", "count"), Avg_Velo=("release_speed", "mean"), Avg_Spin=("release_spin_rate", "mean"))
                .rename(columns={"Avg_Velo": "Avg Velo (mph)", "Avg_Spin": "Avg Spin (RPM)"})
                .round(1)
                .sort_values("Count", ascending=False)
            )
            st.dataframe(breakdown)

        colors = pitch_color_map(df["pitch_type"].dropna().unique().tolist())
        tab1, tab2, tab3, tab4 = st.tabs(["Strike Zone", "Pitch Movement", "Velocity", "Pitch Sequence"])

        with tab1:
            st.markdown("**Pitch location at home plate (catcher's view)**")
            loc_df = df.dropna(subset=["plate_x", "plate_z"])
            if loc_df.empty:
                st.info("No plate location data available.")
            else:
                fig = px.scatter(
                    loc_df, x="plate_x", y="plate_z", color="pitch_name",
                    hover_data={"release_speed": True, "description": True, "plate_x": False, "plate_z": False},
                    labels={"plate_x": "Horizontal (ft)", "plate_z": "Vertical (ft)", "pitch_name": "Pitch"},
                    title="Pitch Locations",
                )
                fig.add_shape(type="rect", x0=-0.83, x1=0.83, y0=1.5, y1=3.5,
                              line=dict(color="black", width=2), fillcolor="rgba(0,0,0,0)")
                fig.update_layout(xaxis=dict(range=[-2.5, 2.5]), yaxis=dict(range=[0, 5]))
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.markdown("**Horizontal vs vertical break (inches from expected straight path)**")
            move_df = df.dropna(subset=["pfx_x", "pfx_z"]).copy()
            move_df["pfx_x_in"] = move_df["pfx_x"] * 12
            move_df["pfx_z_in"] = move_df["pfx_z"] * 12
            if move_df.empty:
                st.info("No movement data available.")
            else:
                fig = px.scatter(
                    move_df, x="pfx_x_in", y="pfx_z_in", color="pitch_name",
                    hover_data={"release_spin_rate": True, "release_speed": True, "pfx_x_in": False, "pfx_z_in": False},
                    labels={"pfx_x_in": "Horizontal Break (in)", "pfx_z_in": "Vertical Break (in)", "pitch_name": "Pitch"},
                    title="Pitch Movement Profile",
                )
                fig.add_hline(y=0, line_dash="dot", line_color="gray")
                fig.add_vline(x=0, line_dash="dot", line_color="gray")
                st.plotly_chart(fig, use_container_width=True)

        with tab3:
            st.markdown("**Velocity distribution per pitch type**")
            velo_df = df.dropna(subset=["release_speed", "pitch_name"])
            if velo_df.empty:
                st.info("No velocity data available.")
            else:
                fig = px.violin(
                    velo_df, x="pitch_name", y="release_speed", color="pitch_name",
                    box=True, points="all",
                    labels={"pitch_name": "Pitch Type", "release_speed": "Velocity (mph)"},
                    title="Velocity by Pitch Type",
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with tab4:
            st.markdown("**Velocity over the course of the game, colored by pitch type**")
            seq_df = df.dropna(subset=["release_speed", "pitch_name"]).copy()
            seq_df["pitch_number"] = range(1, len(seq_df) + 1)
            if seq_df.empty:
                st.info("No sequence data available.")
            else:
                fig = px.scatter(
                    seq_df, x="pitch_number", y="release_speed", color="pitch_name", symbol="description",
                    hover_data={"inning": True, "balls": True, "strikes": True, "description": True, "pitch_number": False},
                    labels={"pitch_number": "Pitch #", "release_speed": "Velocity (mph)", "pitch_name": "Pitch"},
                    title="Pitch Sequence",
                )
                for pname, group in seq_df.groupby("pitch_name"):
                    if len(group) >= 3:
                        fig.add_trace(go.Scatter(
                            x=group["pitch_number"],
                            y=group["release_speed"].rolling(3, min_periods=1).mean(),
                            mode="lines", line=dict(width=1, dash="dot"),
                            showlegend=False, name=f"{pname} trend",
                        ))
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Enter a pitcher name in the sidebar and click **Load Data**.")
