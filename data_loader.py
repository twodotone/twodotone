# data_loader.py

import streamlit as st
import nfl_data_py as nfl
import pandas as pd

@st.cache_data(ttl=3600)
def load_schedule_and_weekly_data(year):
    schedule_df = nfl.import_schedules([year])
    weekly_df = nfl.import_weekly_data([year])
    team_desc_df = nfl.import_team_desc()
    return schedule_df, weekly_df, team_desc_df

@st.cache_data(ttl=3600)
def load_historical_data(years):
    all_schedules = []
    for year in years:
        try:
            schedule = nfl.import_schedules([year])
            all_schedules.append(schedule)
        except Exception as e:
            print(f"Could not load schedule for year {year}: {e}")
    if not all_schedules:
        return pd.DataFrame()
    historical_schedule_df = pd.concat(all_schedules, ignore_index=True)
    return historical_schedule_df

@st.cache_data
def load_full_season_pbp(year):
    pbp_df = nfl.import_pbp_data([year])
    return pbp_df