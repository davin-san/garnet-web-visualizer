import streamlit as st
import subprocess
import shlex
from utils.parse_stats import parse_stats_file, save_run_data
from utils.config_manager import ConfigManager

# --- Page Setup ---
st.set_page_config(layout="wide")
st.title("System Configuration Adjuster")

st.sidebar.header("Instructions")
st.sidebar.info(
    "1. **Configure** the system using the panels below.\n"
    "2. **Review** the auto-generated command.\n"
    "3. **Click Run** to start the simulation."
)

# --- State Initialization ---
# Central place to define all keys this page will use in the session state.
if 'run_triggered' not in st.session_state:
    st.session_state.run_triggered = False
    st.session_state.is_running = False
    st.session_state.command_output = ""
    st.session_state.command_error = ""
    st.session_state.last_run_messages = []

# --- Initialize the Config Manager ---
# This handles all config-related state, widgets, and command generation.
config_manager = ConfigManager(session_state_key='config')
config_manager.display_widgets(exclude_key='')

# ==============================================================================
# --- Generated Command and Execution ---
# ==============================================================================
st.header("Generated Command & Configuration")
command = config_manager.generate_command_string()
st.code(command, language="bash")

button_label = "Running..." if st.session_state.is_running else "Run Command"
if st.button(button_label, disabled=st.session_state.is_running):
    st.session_state.run_triggered = True
    st.rerun()

# --- Execution Logic ---
if st.session_state.run_triggered:
    st.session_state.run_triggered = False  # Reset the trigger
    st.session_state.is_running = True
    st.session_state.last_run_messages = [] # Clear previous messages
    
    command_list = shlex.split(command)
    try:
        with st.spinner('🚀 Executing gem5 simulation... Please wait.'):
            result = subprocess.run(command_list, capture_output=True, text=True, check=False)
            st.session_state.command_output = result.stdout
            st.session_state.command_error = result.stderr

        if result.returncode == 0:
            st.session_state.last_run_messages.append(("success", "✅ Simulation finished successfully!"))
            with st.spinner("💾 Parsing and saving statistics..."):
                parsed_stats = parse_stats_file() 
                if parsed_stats:
                    run_name = save_run_data(config_manager.config, parsed_stats)
                    st.session_state.last_run_messages.append(("info", f"📈 Statistics saved to '{run_name}'!"))
                else:
                    st.session_state.last_run_messages.append(("warning", "⚠️ Could not find or parse stats.txt."))
        else:
            st.session_state.last_run_messages.append(("error", f"❌ Command failed with return code: {result.returncode}"))
    except FileNotFoundError:
        msg = f"Command failed. The executable '{command_list[0]}' was not found."
        st.session_state.last_run_messages.append(("error", msg))
        st.session_state.command_error = msg
    except Exception as e:
        st.session_state.last_run_messages.append(("error", f"An unexpected error occurred: {e}"))
        st.session_state.command_error = str(e)
    finally:
        st.session_state.is_running = False
        st.rerun() # Rerun one last time to update the button state

# --- Display Last Run Results ---
if st.session_state.last_run_messages:
    st.markdown("---")
    st.subheader("Last Run Status")
    for msg_type, msg_text in st.session_state.last_run_messages:
        getattr(st, msg_type)(msg_text) # Calls st.success, st.error, etc.

if st.session_state.command_output:
    with st.expander("Standard Output", expanded=True):
        st.code(st.session_state.command_output, language="text")

if st.session_state.command_error:
    with st.expander("Standard Error", expanded=True):
        st.code(st.session_state.command_error, language="text")

# --- Full Configuration Viewer ---
with st.expander("View Full Configuration JSON"):
    st.json(config_manager.config)