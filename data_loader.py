import streamlit as st
import pandas as pd
import os

@st.cache_data(show_spinner="Loading play-by-play data for {year}...")
def load_full_season_pbp(year):
    """
    Loads the full play-by-play dataset for a given year from a local parquet file.
    """
    file_path = os.path.join("data", f"pbp_{year}.parquet")
    
    try:
        pbp_df = pd.read_parquet(file_path)
        return pbp_df
    except FileNotFoundError:
        st.error(f"Data file not found for {year} at '{file_path}'. Please ensure the data has been downloaded.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Failed to load data for {year}. The file may be corrupt. Error: {e}")
        return pd.DataFrame()
