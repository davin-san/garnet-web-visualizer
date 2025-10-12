import streamlit as st
import json
import os
import pandas as pd
import shutil

def get_config_diff(selected_data):
    """
    Identifies and returns the configuration parameters that differ among the selected runs.

    Args:
        selected_data (list): A list of dictionaries, where each dictionary is the parsed
                              JSON data from a selected file.

    Returns:
        pandas.DataFrame: A DataFrame showing the configuration parameters that vary
                          across the selected runs. Rows are parameters, and columns are runs.
                          Returns an empty DataFrame if no differences are found.
    """
    if not selected_data or len(selected_data) < 2:
        return pd.DataFrame()

    # Create a DataFrame from the config part of each selected file
    configs = {data['run_name']: data['config'] for data in selected_data}
    config_df = pd.DataFrame(configs).reset_index().rename(columns={'index': 'Parameter'})

    # Find rows (parameters) where not all values are the same across the runs
    # We check for more than 1 unique value, ignoring the parameter name itself
    nunique = config_df.drop('Parameter', axis=1).nunique(axis=1)
    diff_mask = nunique > 1
    
    # Filter the DataFrame to show only differing parameters and set the index
    diff_df = config_df[diff_mask].set_index('Parameter')
    
    return diff_df

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(layout="wide")
    st.title("JSON Run Data Analyzer")

    data_dir = 'run_data'

    st.sidebar.header("Instructions")
    st.sidebar.info(
        "1. **Select Runs**: Choose one or more completed simulation runs from the dropdown menu.\n"
        "2. **Choose Statistic**: Pick a simulation output (e.g., latency) to plot on the chart.\n"
        "3. **Analyze Results**: Compare configuration differences and visualize the selected statistic across runs."
    )

    # --- New Feature: Delete All Runs ---
    st.sidebar.header("Manage Runs")
    with st.sidebar.expander("⚠️ Delete All Runs"):
        st.warning("This will permanently delete all JSON files in the 'run_data' folder.")
        # Add a button to confirm the deletion
        if st.button("Confirm and Delete All"):
            if os.path.exists(data_dir) and os.path.isdir(data_dir):
                try:
                    # --- START OF CHANGE ---
                    # Loop through all files in the directory and delete them
                    for filename in os.listdir(data_dir):
                        file_path = os.path.join(data_dir, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    # --- END OF CHANGE ---
                    st.toast("All runs have been deleted! ✨")
                    st.rerun() # Rerun the script to refresh the file list
                except Exception as e:
                    st.error(f"Error deleting files: {e}")
            else:
                st.info("Run directory is already empty or does not exist.")

    # --- 1. File Selection ---
    if not os.path.exists(data_dir):
        st.warning(f"The '{data_dir}' directory was not found. Please create it and add your JSON files.")
        # Create a dummy directory and sample file for demonstration
        os.makedirs(data_dir)
        sample_json_path = os.path.join(data_dir, 'sample_run.json')
        sample_data = {
            "run_name": "run_2025-09-23_17-22-50", "timestamp": "2025-09-23_17-22-50",
            "config": {"num_cpus": 16, "injectionrate": 0.1, "mem_size": "512MB"},
            "stats": {"simSeconds": 0.0, "hostSeconds": 0.22, "system.ruby.network.average_flit_latency": 5000.0}
        }
        with open(sample_json_path, 'w') as f:
            json.dump(sample_data, f, indent=4)
        st.info(f"A sample file '{sample_json_path}' has been created for you.")
        
    try:
        json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        if not json_files:
            st.warning(f"No JSON files found in the '{data_dir}' directory.")
            return
    except FileNotFoundError:
        st.error(f"Error: The directory '{data_dir}' does not exist.")
        return

    selected_files = st.multiselect(
        "Select JSON files to analyze:",
        options=json_files,
        default=[]
    )

    if not selected_files:
        st.info("Please select one or more JSON files to begin analysis.")
        return

    # --- 2. Load and Process Data ---
    all_data = []
    stat_keys = set()
    for file_name in selected_files:
        file_path = os.path.join(data_dir, file_name)
        with open(file_path, 'r') as f:
            data = json.load(f)
            all_data.append(data)
            if 'stats' in data:
                stat_keys.update(data['stats'].keys())
    
    sorted_stat_keys = sorted(list(stat_keys))

    # --- 3. Stat Selection ---
    st.header("Select Statistic to Plot")
    y_axis_stat = st.selectbox(
        "Choose the value for the Y-axis:",
        options=sorted_stat_keys,
        index=0 if sorted_stat_keys else -1
    )

    # --- 4. Display Differences and Plot ---
    if y_axis_stat:
        st.header("Configuration Differences")
        if len(selected_files) > 1:
            config_diff_df = get_config_diff(all_data)
            if not config_diff_df.empty:
                st.dataframe(config_diff_df.astype(str), width='stretch')
            else:
                st.success("No differences found in the configuration sections of the selected files.")
        else:
            st.info("Select at least two files to compare their configurations.")

        st.header(f"Graph of '{y_axis_stat}'")
        
        # Prepare data for plotting
        # 1. Robustly extract and clean data for plotting
        plot_values = []
        for d in all_data:
            # Get the raw value, which could be a number, string ("nan"), or None
            raw_value = d.get('stats', {}).get(y_axis_stat)
            
            # Try to convert to float, defaulting to 0.0 on failure.
            # This correctly handles numeric values and safely converts non-numeric
            # data (like the "nan" string for l1_overall_hit_rate) to zero.
            try:
                plot_values.append(float(raw_value))
            except (ValueError, TypeError):
                plot_values.append(0.0)

        # 2. Prepare data for the DataFrame with a simple column name
        plot_data = {
            'run_name': [d['run_name'] for d in all_data],
            'value': plot_values  # Use a simple, generic name for the y-axis data
        }
        plot_df = pd.DataFrame(plot_data)
        
        # 3. Set 'run_name' as the index for the x-axis labels
        plot_df = plot_df.set_index('run_name')

        # 4. Create the plot
        # Streamlit will now correctly plot the 'value' column.
        st.bar_chart(plot_df)

if __name__ == '__main__':
    main()