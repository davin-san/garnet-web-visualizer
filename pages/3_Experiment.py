import streamlit as st
import pandas as pd
import os
import shutil
import subprocess
import shlex
import sys
import json
from utils.parse_stats import parse_stats_file, save_experiment_run_data
from utils.config_manager import ConfigManager

# --- Add project root to the Python path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

st.set_page_config(layout="wide")
st.title("Experiment Runner")

# --- Sidebar ---
st.sidebar.header("Instructions")
st.sidebar.info(
    "1. **Select Variable**: Choose the independent variable for the experiment (e.g., injection rate).\n"
    "2. **Define Values**: Enter a comma-separated list of values to test.\n"
    "3. **Configure**: Set the fixed parameters for all simulation runs.\n"
    "4. **Run Experiment**: This will execute a simulation for each value.\n"
    "5. **Analyze**: After the runs complete, select a result statistic to visualize."
)

# --- Constants and State Initialization ---
EXPERIMENT_DIR = "experiment_runs"
if 'experiment_running' not in st.session_state:
    st.session_state.experiment_running = False
if 'experiment_results' not in st.session_state:
    st.session_state.experiment_results = None
if 'last_run_x_axis' not in st.session_state:
    st.session_state.last_run_x_axis = None

# --- Initialize Config Manager ---
exp_config_manager = ConfigManager(session_state_key='exp_config')

# --- UI for Variable Selection ---
st.header("1. Select Independent Variable (X-Axis)")
x_axis_options = list(exp_config_manager.DEFAULTS.keys())
excluded_options = ['gem5_path', 'script_path', 'mem_type', 'synthetic', 'topology']
filtered_x_options = [opt for opt in x_axis_options if opt not in excluded_options]
default_x_index = filtered_x_options.index('injectionrate') if 'injectionrate' in filtered_x_options else 0
x_axis_var = st.selectbox("Variable to sweep:", options=filtered_x_options, index=default_x_index)

st.header("2. Define Values for Selected Variable")
x_values_str = st.text_input(f"Enter comma-separated values for '{x_axis_var}'", "0.01, 0.02, 0.03, 0.04")

# --- Configuration Section ---
st.header("3. Configure Base Simulation Parameters")
with st.expander("Adjust Fixed Parameters", expanded=False):
    exp_config_manager.display_widgets(exclude_key=x_axis_var)

# --- Run Button & Logic ---
st.header("4. Run Experiment")
if st.button("Start Experiment", disabled=st.session_state.experiment_running):
    st.session_state.experiment_running = True
    st.session_state.experiment_results = None
    st.session_state.last_run_x_axis = x_axis_var 
    if os.path.exists(EXPERIMENT_DIR):
        shutil.rmtree(EXPERIMENT_DIR)
    os.makedirs(EXPERIMENT_DIR)
    st.rerun()

if st.session_state.experiment_running:
    x_values = [x.strip() for x in x_values_str.split(',') if x.strip()]
    
    st.info(f"Starting experiment with {len(x_values)} runs...")
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, x_val in enumerate(x_values):
        run_x_axis_var = st.session_state.last_run_x_axis
        current_config = exp_config_manager.config.copy()
        try:
            # Use float for conversion if it looks like a float, otherwise int
            numeric_val = float(x_val) if '.' in x_val else int(x_val)
            current_config[run_x_axis_var] = numeric_val
        except ValueError:
            current_config[run_x_axis_var] = x_val # Fallback for non-numeric values
        
        status_text.text(f"Running simulation {i+1}/{len(x_values)} with {run_x_axis_var} = {x_val}...")
        
        original_value = exp_config_manager.config.get(run_x_axis_var)
        exp_config_manager.config[run_x_axis_var] = current_config[run_x_axis_var]
        command = exp_config_manager.generate_command_string()
        if original_value is not None:
             exp_config_manager.config[run_x_axis_var] = original_value
        
        command_list = shlex.split(command)

        try:
            result = subprocess.run(command_list, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                stats = parse_stats_file()
                save_experiment_run_data(current_config, stats, output_dir=EXPERIMENT_DIR)
            else:
                st.error(f"Simulation failed for {run_x_axis_var}={x_val}. Stderr:")
                st.code(result.stderr)
        except Exception as e:
            st.error(f"A Python-level error occurred for {run_x_axis_var}={x_val}: {e}")

        progress_bar.progress((i + 1) / len(x_values))

    st.session_state.experiment_running = False
    status_text.success("Experiment finished!")
    st.rerun()

# --- Post-Run Analysis and Visualization ---
st.header("5. Analyze and Visualize Results")

# Use the stored x-axis variable from the last run for analysis
analysis_x_axis_var = st.session_state.get('last_run_x_axis')

if not analysis_x_axis_var or not os.path.exists(EXPERIMENT_DIR) or not os.listdir(EXPERIMENT_DIR):
    st.info("No experiment data found. Run an experiment to see results here.")
else:
    results_data = []
    all_stat_keys = set()
    for filename in sorted(os.listdir(EXPERIMENT_DIR)):
        if filename.endswith('.json'):
            filepath = os.path.join(EXPERIMENT_DIR, filename)
            with open(filepath, 'r') as f:
                data = json.load(f)
                results_data.append(data)
                if data.get('stats'):
                    all_stat_keys.update(data['stats'].keys())

    if not results_data:
        st.warning("No valid JSON result files found in the experiment directory.")
    else:
        sorted_stat_keys = sorted(list(all_stat_keys))
        
        default_y_index = 0
        try:
            default_y_var = next(key for key in sorted_stat_keys if key not in ['simSeconds', 'hostSeconds'])
            default_y_index = sorted_stat_keys.index(default_y_var)
        except StopIteration:
            pass

        y_axis_var = st.selectbox(
            "Select statistic to plot (Y-Axis):",
            options=sorted_stat_keys,
            index=default_y_index
        )
        
        plot_points = []
        for data in results_data:
            x_val = data.get('config', {}).get(analysis_x_axis_var)
            y_val_raw = data.get('stats', {}).get(y_axis_var)

            if x_val is not None and y_val_raw is not None:
                try:
                    y_val_numeric = float(y_val_raw) 
                    plot_points.append({analysis_x_axis_var: x_val, y_axis_var: y_val_numeric})
                except (ValueError, TypeError):
                    pass

        if plot_points:
            df = pd.DataFrame(plot_points)
            df = df.sort_values(by=analysis_x_axis_var).reset_index(drop=True)

            st.subheader(f"Plot of {y_axis_var} vs. {analysis_x_axis_var}")
            if y_axis_var in df.columns and analysis_x_axis_var in df.columns:
                df_for_plot = df[[analysis_x_axis_var, y_axis_var]].copy()
                df_for_plot.rename(columns={
                    analysis_x_axis_var: 'X-Axis',
                    y_axis_var: 'Y-Axis'
                }, inplace=True)
                
                st.line_chart(df_for_plot, x='X-Axis', y='Y-Axis')
            
            with st.expander("View Raw Data Table"):
                # Display the original dataframe with full names for clarity
                st.dataframe(df)
        else:
            st.warning(f"No numeric data available for the selected statistic '{y_axis_var}'.")