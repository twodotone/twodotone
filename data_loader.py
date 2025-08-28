import streamlit as st
import pandas as pd
import nfl_data_py as nfl

@st.cache_data(show_spinner=f"Loading play-by-play data for {{year}}...")
def load_full_season_pbp(year):
    """
    Loads the full play-by-play dataset for a given year.
    Includes a more robust error handling block to prevent crashes on data fetch failures.
    """
    try:
        # The nfl_data_py library can sometimes have issues fetching data.
        # This block will catch potential errors during the download.
        pbp_df = nfl.import_pbp_data([year])
        if pbp_df.empty:
            st.error(f"No play-by-play data could be loaded for the {year} season. The data source may be temporarily unavailable.")
            return pd.DataFrame()
        return pbp_df
    except Exception as e:
        # This is a general catch-all. The nfl_data_py library has a bug
        # where it can raise a NameError on a failed download. This prevents the app from crashing.
        st.error(f"Failed to download data for the {year} season. The data source may be down. Please try again later. Error: {e}")
        return pd.DataFrame()
