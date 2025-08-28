# app.py

import streamlit as st
import pandas as pd
import nfl_data_py as nfl
from data_loader import load_full_season_pbp
from stats_calculator import (
    get_last_n_games_pbp,
    calculate_granular_epa_stats,
    calculate_weighted_stats,
    generate_stable_matchup_line
)

# --- Page & Sidebar Configuration ---
st.set_page_config(page_title="NFL Matchup Analyzer", layout="wide")
st.title('🏈 NFL Matchup Analyzer')
st.sidebar.header('Season Settings')
CURRENT_YEAR = st.sidebar.selectbox('Year', [2025, 2024, 2023, 2022], index=0)
CURRENT_WEEK = st.sidebar.number_input('Week', min_value=1, max_value=18, value=1, step=1)

st.sidebar.header('Model Settings')
use_sos_adjustment = st.sidebar.checkbox('Apply Strength of Schedule Adjustment', value=True)

# --- Data Loading ---
try:
    team_desc = nfl.import_team_desc()
    schedule_data = nfl.import_schedules([CURRENT_YEAR])
except Exception as e:
    st.error(f"Could not load schedule or team data for {CURRENT_YEAR}. Error: {e}")
    st.stop()

# --- Main Page: Matchup Selection ---
st.header(f'Week {CURRENT_WEEK} Matchups for the {CURRENT_YEAR} Season')
week_schedule = schedule_data[schedule_data['week'] == CURRENT_WEEK].copy()
if week_schedule.empty:
    st.warning(f"No schedule found for Week {CURRENT_WEEK} of the {CURRENT_YEAR} season.")
else:
    week_schedule['game_description'] = week_schedule['away_team'] + ' @ ' + week_schedule['home_team']
    game_options = ["Select a Game to Analyze"] + week_schedule['game_description'].tolist()
    selected_game_str = st.selectbox('Choose a matchup:', game_options)

    if selected_game_str != "Select a Game to Analyze":
        game_details = week_schedule[week_schedule['game_description'] == selected_game_str].iloc[0]
        away_abbr, home_abbr = game_details['away_team'], game_details['home_team']
        
        # Display Betting Odds Banner
        st.subheader("Betting Odds & Game Info")
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns(5)
            away_logo = team_desc.loc[team_desc['team_abbr'] == away_abbr, 'team_logo_espn'].values[0]
            home_logo = team_desc.loc[team_desc['team_abbr'] == home_abbr, 'team_logo_espn'].values[0]
            
            home_ml = game_details.get('home_moneyline')
            away_ml = game_details.get('away_moneyline')
            spread_magnitude = abs(game_details.get('spread_line', 0))

            if home_ml is not None and away_ml is not None:
                if home_ml < away_ml:
                    home_spread_vegas = -spread_magnitude
                    away_spread_vegas = spread_magnitude
                else:
                    home_spread_vegas = spread_magnitude
                    away_spread_vegas = -spread_magnitude
            else:
                # Fallback if moneyline is not available
                home_spread_vegas = game_details.get('spread_line', 0)
                away_spread_vegas = -home_spread_vegas
            
            total_line = game_details.get('total_line', 0)
            
            col1.image(away_logo, width=70)
            col2.metric("Away Spread", f"{away_spread_vegas:+.1f}")
            col3.metric("Over/Under", f"{total_line:.1f}")
            col4.metric("Home Spread", f"{home_spread_vegas:+.1f}")
            col5.image(home_logo, width=70)

        # --- Data Prep based on Mode ---
        
        if CURRENT_YEAR >= 2025:
            st.info("Displaying **live predictions** for the upcoming season based on prior year data.")
            prediction_year = CURRENT_YEAR - 1
            pbp_data_for_stats = load_full_season_pbp(prediction_year)
        else:
            st.info("Displaying **interactive backtest** for a completed historical game.")
            if CURRENT_WEEK < 4: st.warning("Model performance may be unreliable with less than 3 weeks of data.")
            prediction_year = CURRENT_YEAR
            pbp_data_full_season = load_full_season_pbp(prediction_year)
            pbp_data_for_stats = pbp_data_full_season[pbp_data_full_season['week'] < CURRENT_WEEK]

        # --- Add this check to gracefully stop if data loading failed ---
        if pbp_data_for_stats.empty:
            st.warning("Could not retrieve the necessary play-by-play data. Please try again later.")
            st.stop() # This stops the app from running further.

        # --- Stat Calculation ---
        with st.spinner('Calculating team stats...'):
            away_stats_std = calculate_granular_epa_stats(pbp_data_for_stats, away_abbr, use_sos_adjustment)
            home_stats_std = calculate_granular_epa_stats(pbp_data_for_stats, home_abbr, use_sos_adjustment)

            
            # The generated spread is from the home team's perspective. A positive value means home is favored.
            # We must invert it to match the standard convention (favorite is negative).
            model_home_spread = -generate_stable_matchup_line(home_stats_std, away_stats_std)
            model_away_spread = -model_home_spread

        st.subheader("Prediction Engine")
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("Vegas Line (Home Spread)", f"{home_spread_vegas:+.1f}")
            col2.metric("Model Spread (Home)", f"{model_home_spread:+.1f}")
            
            model_edge = home_spread_vegas - model_home_spread
            pick = home_abbr if model_edge > 0 else away_abbr
            col3.metric("Model Edge", f"{abs(model_edge):.1f} pts on {pick}")

        # --- Recency Weighting UI & Calculation ---
        st.subheader("Model Refinements (Recency Weighting)")
        with st.container(border=True):
            col1, col2 = st.columns(2)
            recent_games_window = col1.slider('Recent Games Window', 4, 12, 8, 1, help="Adjust the lookback window for 'recent form'.")
            recent_form_weight_pct = col2.slider('Recent Form Weight (%)', 0, 50, 20, 5, help="Adjust how much to weight recent form vs. full-season data.")
            recent_form_weight = recent_form_weight_pct / 100.0
            full_season_weight = 1 - recent_form_weight

            with st.spinner('Calculating weighted model...'):
                pbp_away_recent = get_last_n_games_pbp(pbp_data_for_stats, away_abbr, recent_games_window)
                pbp_home_recent = get_last_n_games_pbp(pbp_data_for_stats, home_abbr, recent_games_window)
                away_stats_recent = calculate_granular_epa_stats(pbp_away_recent, away_abbr, use_sos_adjustment)
                home_stats_recent = calculate_granular_epa_stats(pbp_home_recent, home_abbr, use_sos_adjustment)

                away_stats_w = calculate_weighted_stats(away_stats_std, away_stats_recent, full_season_weight, recent_form_weight)
                home_stats_w = calculate_weighted_stats(home_stats_std, home_stats_recent, full_season_weight, recent_form_weight)
                
                # We must invert it to match the standard convention (favorite is negative).
                weighted_model_home_spread = -generate_stable_matchup_line(home_stats_w, away_stats_w)
                weighted_model_away_spread = -weighted_model_home_spread

            st.metric("Weighted Model Spread", f"{weighted_model_home_spread:+.1f}", f"{weighted_model_home_spread - model_home_spread:+.1f} vs. Standard", delta_color="off")

        # --- Historical Backtest Display ---
        if CURRENT_YEAR < 2025:
            st.subheader("Historical Game Backtest")
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Vegas Line (Home)", f"{home_spread_vegas:+.1f}")
                col2.metric("Model's Line (Home)", f"{weighted_model_home_spread:+.1f}")
                
                model_edge = home_spread_vegas - weighted_model_home_spread
                pick = home_abbr if model_edge > 0 else away_abbr
                col3.metric("Model Edge", f"{abs(model_edge):.1f} pts on {pick}")

                actual_home_margin = game_details['result']
                final_score = f"Final: {game_details['away_score']} - {game_details['home_score']}"
                col4.metric("Actual Margin (Home)", f"{actual_home_margin:+.0f}", final_score)
                
                st.divider()

                if (actual_home_margin + home_spread_vegas) > 0:
                    covering_team = home_abbr
                elif (actual_home_margin + home_spread_vegas) < 0:
                    covering_team = away_abbr
                else:
                    covering_team = "Push"
                
                if covering_team == "Push":
                    st.warning(f"**PUSH.** The model identified value on **{pick}**, but the game landed on the number.")
                elif pick == covering_team:
                    st.success(f"**MODEL WIN.** The model identified value on **{pick}** and they **COVERED** the spread.")
                else:
                    st.error(f"**MODEL LOSS.** The model identified value on **{pick}**, but the **{covering_team}** covered the spread.")
