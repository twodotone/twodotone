import pandas as pd
import streamlit as st

@st.cache_data
def get_last_n_games_pbp(full_pbp_df, team_abbr, n_games):
    """
    Extracts the play-by-play data for the last N regular season games for a given team.
    """
    team_games = full_pbp_df[((full_pbp_df['home_team'] == team_abbr) | (full_pbp_df['away_team'] == team_abbr)) & (full_pbp_df['season_type'] == 'REG')]
    if team_games.empty:
        return pd.DataFrame()
    unique_games = team_games[['game_id', 'week']].drop_duplicates().sort_values(by='week', ascending=False)
    last_n_game_ids = unique_games['game_id'].head(n_games).tolist()
    return full_pbp_df[full_pbp_df['game_id'].isin(last_n_game_ids)]

#@st.cache_data
def calculate_explosive_play_rates(_pbp_df):
    """
    Calculates the rate of explosive plays (runs >= 10 yards, passes >= 20 yards).
    """
    pbp_df = _pbp_df.copy()
    explosive_runs = pbp_df[(pbp_df['play_type'] == 'run') & (pbp_df['yards_gained'] >= 10)]
    explosive_passes = pbp_df[(pbp_df['play_type'] == 'pass') & (pbp_df['yards_gained'] >= 20)]
    total_runs = pbp_df[pbp_df['play_type'] == 'run'].shape[0]
    total_passes = pbp_df[pbp_df['play_type'] == 'pass'].shape[0]
    total_plays = total_runs + total_passes
    total_explosive_plays = len(explosive_runs) + len(explosive_passes)
    return total_explosive_plays / total_plays if total_plays > 0 else 0

#@st.cache_data
def calculate_granular_epa_stats(_pbp_df, team_abbr, use_sos_adjustment=True):
    """
    Calculates opponent-adjusted EPA stats for Offense and Defense.
    Can be toggled to calculate raw (unadjusted) EPA.
    """
    if _pbp_df.empty:
        return {}

    pbp_reg = _pbp_df[_pbp_df['season_type'] == 'REG'].copy()
    if pbp_reg.empty:
        return {}
    
    stats = {}
    
    # --- Offense and Defense Calculations ---
    pbp_off_def = pbp_reg[(pbp_reg['play_type'] == 'pass') | (pbp_reg['play_type'] == 'run')].copy()
    if not pbp_off_def.empty:
        # Calculate league-wide baselines for SOS adjustment
        lg_off_rush_epa = pbp_off_def[pbp_off_def['play_type'] == 'run'].groupby('posteam')['epa'].mean().rename('lg_off_rush_epa')
        lg_off_pass_epa = pbp_off_def[pbp_off_def['play_type'] == 'pass'].groupby('posteam')['epa'].mean().rename('lg_off_pass_epa')
        lg_def_rush_epa = pbp_off_def[pbp_off_def['play_type'] == 'run'].groupby('defteam')['epa'].mean().rename('lg_def_rush_epa')
        lg_def_pass_epa = pbp_off_def[pbp_off_def['play_type'] == 'pass'].groupby('defteam')['epa'].mean().rename('lg_def_pass_epa')

        off_plays = pbp_off_def[pbp_off_def['posteam'] == team_abbr]
        def_plays = pbp_off_def[pbp_off_def['defteam'] == team_abbr]

        if not off_plays.empty:
            total_plays = len(off_plays)
            rush_plays = off_plays[off_plays['play_type'] == 'run']
            pass_plays = off_plays[off_plays['play_type'] == 'pass']
            stats['Rush_Pct'] = len(rush_plays) / total_plays if total_plays > 0 else 0
            stats['Pass_Pct'] = len(pass_plays) / total_plays if total_plays > 0 else 0
            
            if not rush_plays.empty:
                if use_sos_adjustment:
                    # Join opponent defensive averages to each play
                    rush_plays_adj = rush_plays.merge(lg_def_rush_epa, left_on='defteam', right_index=True, how='left')
                    # Subtract the opponent's average from each play's EPA
                    stats['Off_Rush_EPA'] = (rush_plays_adj['epa'] - rush_plays_adj['lg_def_rush_epa']).mean()
                else:
                    stats['Off_Rush_EPA'] = rush_plays['epa'].mean()

            if not pass_plays.empty:
                if use_sos_adjustment:
                    pass_plays_adj = pass_plays.merge(lg_def_pass_epa, left_on='defteam', right_index=True, how='left')
                    stats['Off_Pass_EPA'] = (pass_plays_adj['epa'] - pass_plays_adj['lg_def_pass_epa']).mean()
                else:
                    stats['Off_Pass_EPA'] = pass_plays['epa'].mean()

            stats['Off_Explosive_Rate'] = calculate_explosive_play_rates(off_plays)

        if not def_plays.empty:
            rush_plays_faced = def_plays[def_plays['play_type'] == 'run']
            pass_plays_faced = def_plays[def_plays['play_type'] == 'pass']

            if not rush_plays_faced.empty:
                if use_sos_adjustment:
                    rush_plays_faced_adj = rush_plays_faced.merge(lg_off_rush_epa, left_on='posteam', right_index=True, how='left')
                    stats['Def_Rush_EPA'] = (rush_plays_faced_adj['epa'] - rush_plays_faced_adj['lg_off_rush_epa']).mean()
                else:
                    stats['Def_Rush_EPA'] = rush_plays_faced['epa'].mean()

            if not pass_plays_faced.empty:
                if use_sos_adjustment:
                    pass_plays_faced_adj = pass_plays_faced.merge(lg_off_pass_epa, left_on='posteam', right_index=True, how='left')
                    stats['Def_Pass_EPA'] = (pass_plays_faced_adj['epa'] - pass_plays_faced_adj['lg_off_pass_epa']).mean()
                else:
                    stats['Def_Pass_EPA'] = pass_plays_faced['epa'].mean()
                
            stats['Def_Explosive_Rate'] = calculate_explosive_play_rates(def_plays)
            
    # --- Pace of Play Calculation ---
    team_plays = pbp_reg[(pbp_reg['posteam'] == team_abbr) & ((pbp_reg['play_type'] == 'pass') | (pbp_reg['play_type'] == 'run'))]
    if not team_plays.empty:
        # Calculate plays per game
        games_played = team_plays['game_id'].nunique()
        total_plays = len(team_plays)
        stats['plays_per_game'] = total_plays / games_played if games_played > 0 else 65 # Default if no games

    return stats

def calculate_weighted_stats(stats_std, stats_recent, full_season_weight, recent_form_weight):
    """
    Calculates a weighted average of full-season and recent stats.
    """
    all_keys = set(stats_std.keys()) | set(stats_recent.keys())
    stats_w = {}
    for key in all_keys:
        # Ensure 'plays_per_game' uses the full season data, not recency-weighted
        if key == 'plays_per_game':
            stats_w[key] = stats_std.get(key, 65)
        else:
            stats_w[key] = (stats_std.get(key, 0) * full_season_weight) + (stats_recent.get(key, 0) * recent_form_weight)
    return stats_w

def generate_stable_matchup_line(home_stats, away_stats):
    """
    Generates a predicted line based on the granular EPA matchup engine.
    HFA and QB Adjustments have been permanently removed from this calculation.
    """
    # Use team average passing EPA
    home_pass_offense_epa = home_stats.get('Off_Pass_EPA', 0)
    away_pass_offense_epa = away_stats.get('Off_Pass_EPA', 0)

    home_rush_outcome = (home_stats.get('Off_Rush_EPA', 0) + away_stats.get('Def_Rush_EPA', 0)) / 2
    home_pass_outcome = (home_pass_offense_epa + away_stats.get('Def_Pass_EPA', 0)) / 2
    home_exp_outcome_per_play = (home_rush_outcome * home_stats.get('Rush_Pct', 0.5)) + \
                                (home_pass_outcome * home_stats.get('Pass_Pct', 0.5))

    away_rush_outcome = (away_stats.get('Off_Rush_EPA', 0) + home_stats.get('Def_Rush_EPA', 0)) / 2
    away_pass_outcome = (away_pass_offense_epa + home_stats.get('Def_Pass_EPA', 0)) / 2
    away_exp_outcome_per_play = (away_rush_outcome * away_stats.get('Rush_Pct', 0.5)) + \
                                (away_pass_outcome * away_stats.get('Pass_Pct', 0.5))

    # Dynamic Pace of Play
    expected_plays = (home_stats.get('plays_per_game', 65) + away_stats.get('plays_per_game', 65)) / 2

    net_adv_per_play = home_exp_outcome_per_play - away_exp_outcome_per_play
    neutral_margin_off_def = net_adv_per_play * expected_plays

    # The final margin IS the spread. HFA is no longer added.
    # A positive margin means the home team is favored.
    return neutral_margin_off_def