import streamlit as st
import re
import subprocess
import shlex
import time
from utils.parse_stats import parse_stats_file, save_run_data

# Set the page configuration for a wider layout
st.set_page_config(layout="wide")

# Custom CSS for a green button
st.markdown("""
<style>
/* Targets the specific button container to make the button green */
div.stButton > button:first-child {
    background-color: #4CAF50; /* Green */
    color: white;
    border: none;
    padding: 10px 24px;
    text-align: center;
    text-decoration: none;
    display: inline-block;
    font-size: 16px;
    margin: 4px 2px;
    cursor: pointer;
    border-radius: 8px;
}
div.stButton > button:hover {
    background-color: #45a049; /* Darker Green */
}
div.stButton > button:active {
    background-color: #3e8e41; /* Even Darker Green */
}
/* Style for the disabled state */
div.stButton > button:disabled {
    background-color: #cccccc;
    color: #666666;
    border: 1px solid #999999;
}
/* Style for wrapping text in st.code block */
pre code {
    white-space: pre-wrap !important;
    word-wrap: break-word !important;
}
</style>""", unsafe_allow_html=True)


st.title("System Configuration Adjuster")
st.write(
    "Use the widgets below to configure the simulation options. "
    "The selections are summarized at the bottom of the page."
)

st.sidebar.header("Instructions")
st.sidebar.info(
    "1. Configure the system. \n"
    "2. Specify the executable path and hit run command. \n"
    "3. The application will save the run statistics and display the command line output."
)

# --- Default Values for Garnet Synthetic Traffic ---
DEFAULTS = {
    # App config
    'gem5_path': './build/NULL/gem5.debug',
    'script_path': 'configs/example/garnet_synth_traffic.py',
    # System
    'num_cpus': 16,
    'sys_voltage': '1.0V',
    'sys_clock': '1GHz',
    # Simulation Time
    'sim_cycles': 1000,
    'abs_max_tick': 1000000,
    'rel_max_tick': 0,
    'maxtime': 0.0,
    # Memory
    'mem_type': 'DDR3_1600_8x8',
    'mem_size': '512MB',
    'mem_channels': 1,
    'mem_ranks': 2, # Default is None in code, but UI needs a value. 2 is reasonable.
    'enable_dram_powerdown': False,
    'memchecker': False,
    # Cache
    'caches': False,
    'l2cache': False,
    'num_l2caches': 1,
    'num_l3caches': 1,
    'l1d_size': '64kB',
    'l1i_size': '32kB',
    'l2_size': '2MB',
    'l3_size': '16MB',
    'l1d_assoc': 2,
    'l1i_assoc': 2,
    'l2_assoc': 8,
    'l3_assoc': 16,
    'cacheline_size': 64,
    # Ruby and Network
    'ruby': False,
    'ruby_clock': '2GHz',
    'access_backing_store': False,
    'num_dirs': 16, # This will be dynamically set to num_cpus on init
    'recycle_latency': 10,
    'network': 'simple',
    'topology': 'Crossbar',
    'mesh_rows': 1,
    'router_latency': 1,
    'link_latency': 1,
    'link_width_bits': 128,
    'vcs_per_vnet': 4,
    'garnet_deadlock_threshold': 50000,
    'routing_algorithm': 0,
    'network_fault_model': False,
    'garnet_tracer': False,
    # NUMA
    'numa_high_bit': 0,
    'interleaving_bits': 6,
    'xor_low_bit': 0,
    'ports': 16,
    # Traffic Injection
    'synthetic': 'uniform_random',
    'injectionrate': 0.1,
    'precision': 3,
    'inj_vnet': -1,
    'num_packets_max': -1,
    'single_sender_id': -1,
    'single_dest_id': -1,
    # Misc
    'param': '',
    'mem_channels_intlv': 0,
    'external_memory_system': '',
    'tlm_memory': '',
}


# --- State Management and Callbacks ---

def sync_widget(key):
    """Generic callback to sync a widget's value into the main config dict."""
    if key in st.session_state:
        st.session_state.config[key] = st.session_state[key]

def sync_composite_widget(config_key, val_key, unit_key):
    """Callback to combine a number input and a unit selector into one config value."""
    value = st.session_state.get(val_key, 0)
    unit = st.session_state.get(unit_key, '')
    st.session_state.config[config_key] = f"{value}{unit}"

# Add this new function with your other callbacks
def handle_cpu_change():
    """
    Updates num_cpus, syncs num_dirs, and if the network is garnet,
    it calculates and updates a valid mesh-rows value.
    """
    # 1. Get the new CPU value from the widget's state
    new_cpu_val = st.session_state.num_cpus
    
    # 2. Update the config for cpus and dirs (as before)
    st.session_state.config['num_cpus'] = new_cpu_val
    st.session_state.config['num_dirs'] = new_cpu_val

    # 3. If network is garnet, intelligently update mesh_rows
    if st.session_state.config.get('network') == 'garnet':
        # Calculate a reasonable number of rows (integer square root)
        # This provides a good default for a square-ish mesh
        new_mesh_rows = int(new_cpu_val ** 0.5)
        
        # Ensure rows is at least 1 and divides num_cpus, adjust if not
        while new_cpu_val % new_mesh_rows != 0:
            new_mesh_rows -= 1
            if new_mesh_rows == 0:
                new_mesh_rows = 1 # Fallback for prime numbers
                break

        st.session_state.config['mesh_rows'] = new_mesh_rows

def update_network_and_topology():
    """Callback to sync network and automatically update topology."""
    # First, sync the network widget's own value
    new_network_val = st.session_state['network']
    st.session_state.config['network'] = new_network_val

    # Now, update topology based on the new network value
    if new_network_val == 'garnet':
        st.session_state.config['topology'] = 'Mesh_XY'
    elif new_network_val == 'simple':
        st.session_state.config['topology'] = 'Crossbar'

# Initialize session state to hold the configuration
if 'config' not in st.session_state:
    st.session_state.config = DEFAULTS.copy()
    # Default for num_dirs is num_cpus
    st.session_state.config['num_dirs'] = st.session_state.config['num_cpus']
    # Add state for command execution
    st.session_state.run_triggered = False
    st.session_state.last_run_messages = []
    st.session_state.is_running = False
    st.session_state.command_output = None
    st.session_state.command_error = None


def generate_command_string(config, defaults):
    """Generates the command string based on non-default values."""
    executable_path = config.get('gem5_path', DEFAULTS['gem5_path'])
    script_path = config.get('script_path', DEFAULTS['script_path'])
    base_cmd = f"{executable_path} {script_path}"
    args = []
    
    # --- NEW: Check if Garnet is active and define required keys ---
    is_garnet_active = config.get('network') == 'garnet'
    required_garnet_keys = ['num_cpus', 'num_dirs', 'mesh_rows']
    # --- END NEW ---
    
    for key, value in config.items():
        # Skip the paths, as they are part of the base command, not flags
        if key in ['gem5_path', 'script_path']:
            continue

        # If num_dirs is the same as num_cpus, it's redundant and can be omitted
        # because the gem5 script defaults num_dirs to num_cpus if unspecified.
        # This rule does NOT apply to garnet, which requires it explicitly.
        if key == 'num_dirs' and value == config.get('num_cpus') and not is_garnet_active:
            continue

        default_value = defaults.get(key)
        
        # --- MODIFIED: Logic to skip default values ---
        # The original behavior is to skip any value that matches the default.
        if value == default_value:
            # We add an exception: if Garnet is active and the key is one
            # of the required ones, we DO NOT skip it.
            if is_garnet_active and key in required_garnet_keys:
                pass  # Force inclusion by doing nothing here.
            else:
                continue # Otherwise, skip the default value as usual.
        # --- END MODIFIED ---
            
        flag = f"--{key.replace('_', '-')}"
        
        if isinstance(value, bool):
            if value:
                if key == 'garnet_tracer':
                    args.append('--garnet-tracer')
                else:
                    args.append(flag)
        else:
            if str(value).strip() or (str(default_value).strip() and not str(value).strip()):
                 args.append(f"{flag}={value}")
    
    return f"{base_cmd} {' '.join(args)}"

def parse_value_unit(value_str, units):
    """Helper to split a string like '1GHz' into a value and a unit."""
    value_str = str(value_str).strip()
    match = re.match(r"([0-9.]+)\s*([a-zA-Z]+)", value_str)
    if match:
        val, unit = match.groups()
        if unit in units:
            try:
                num_val = float(val)
                return int(num_val) if num_val.is_integer() else num_val, unit
            except ValueError:
                return 0, units[0]
    try:
        num_val = float(value_str)
        return int(num_val) if num_val.is_integer() else num_val, units[0]
    except (ValueError, TypeError):
        return 0, units[0]

# --- UI Component for Composite Value (e.g., Size or Clock) ---
def composite_input(label, config_key, units, help_text=""):
    """Creates a number input and a unit selector for a single config value."""
    st.markdown(f"**{label}** (`--{config_key.replace('_','-')}`)")
    
    default_val, default_unit = parse_value_unit(st.session_state.config[config_key], units)
    
    val_key = f"{config_key}_val"
    unit_key = f"{config_key}_unit"

    col1, col2 = st.columns([2, 1])
    with col1:
        st.number_input(
            label,
            value=default_val,
            key=val_key,
            on_change=sync_composite_widget,
            args=(config_key, val_key, unit_key),
            label_visibility="collapsed",
            step=1
        )
    with col2:
        st.selectbox(
            label + " unit",
            options=units,
            index=units.index(default_unit),
            key=unit_key,
            on_change=sync_composite_widget,
            args=(config_key, val_key, unit_key),
            label_visibility="collapsed"
        )
    if help_text:
        st.caption(help_text)


# ==============================================================================
# --- System, CPU, and Simulation Control ---
# ==============================================================================
with st.expander("System, CPU, and Simulation Control", expanded=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("CPU & System")
        st.number_input(
            'Number of CPUs (`--num-cpus`)',
            min_value=1,
            step=1,
            help="Number of CPUs to simulate. When using the Garnet network, this will also auto-update mesh-rows to a valid value.",
            value=st.session_state.config['num_cpus'],
            key='num_cpus',
            on_change=handle_cpu_change
        )

        st.text_input(
            'System Voltage (`--sys-voltage`)',
            help="Top-level voltage for blocks running at system power supply (e.g., '1.0V').",
            value=st.session_state.config['sys_voltage'],
            key='sys_voltage',
            on_change=sync_widget,
            args=('sys_voltage',)
        )
        
        composite_input("System Clock", "sys_clock", ["kHz", "MHz", "GHz"])

    with col2:
        st.subheader("Simulation Time")
        st.number_input(
            'Absolute Max Tick (`--abs-max-tick`)',
            min_value=0,
            step=1000,
            help="Run to absolute simulated tick specified.",
            value=st.session_state.config['abs_max_tick'],
            key='abs_max_tick',
            on_change=sync_widget,
            args=('abs_max_tick',)
        )
        st.number_input(
            'Relative Max Tick (`--rel-max-tick`)',
            min_value=0,
            step=1000,
            help="Simulate for a specified number of ticks relative to the start tick.",
            value=st.session_state.config['rel_max_tick'],
            key='rel_max_tick',
            on_change=sync_widget,
            args=('rel_max_tick',)
        )
        st.number_input(
            'Max Time (seconds) (`--maxtime`)',
            min_value=0.0,
            format="%.4f",
            help="Run to the specified absolute simulated time in seconds.",
            value=st.session_state.config['maxtime'],
            key='maxtime',
            on_change=sync_widget,
            args=('maxtime',)
        )
        st.number_input(
            'Simulation Cycles (`--sim-cycles`)',
            min_value=0,
            help="Number of simulation cycles to run.",
            value=st.session_state.config['sim_cycles'],
            key='sim_cycles',
            on_change=sync_widget,
            args=('sim_cycles',)
        )

    with col3:
        st.subheader("SimObject Parameters")
        st.text_area(
            "Set Parameter (`--param`)",
            height=200,
            help="Set a SimObject parameter, e.g., 'system.cpu[0].max_insts_all_threads = 42'",
            value=st.session_state.config['param'],
            key='param',
            on_change=sync_widget,
            args=('param',)
        )

# ==============================================================================
# --- Memory Configuration ---
# ==============================================================================
with st.expander("Memory Configuration", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Memory Type & Size")
        mem_types_list = [
            "CfiMemory", "DDR3_1600_8x8", "DDR3_2133_8x8", "DDR4_2400_16x4",
            "DDR4_2400_4x16", "DDR4_2400_8x8", "DRAMInterface", "GDDR5_4000_2x32",
            "HBM_1000_4H_1x128", "HBM_1000_4H_1x64", "HBM_2000_4H_1x64",
            "HMC_2500_1x32", "LPDDR2_S4_1066_1x32", "LPDDR3_1600_1x32",
            "LPDDR5_5500_1x16_8B_BL32", "LPDDR5_5500_1x16_BG_BL16",
            "LPDDR5_5500_1x16_BG_BL32", "LPDDR5_6400_1x16_8B_BL32",
            "LPDDR5_6400_1x16_BG_BL16", "LPDDR5_6400_1x16_BG_BL32",
            "NVMInterface", "NVM_2400_1x64", "QoSMemSinkInterface", "SimpleMemory",
            "WideIO_200_1x128"
        ]
        st.selectbox(
            'Memory Type (`--mem-type`)',
            options=mem_types_list,
            index=mem_types_list.index(st.session_state.config['mem_type']),
            help="Type of memory to use.",
            key='mem_type',
            on_change=sync_widget,
            args=('mem_type',)
        )
        composite_input("Memory Size", "mem_size", ["kB", "MB", "GB", "TB"])

    with col2:
        st.subheader("Channels & Ranks")
        st.number_input(
            'Memory Channels (`--mem-channels`)',
            min_value=1, help="Number of memory channels.",
            value=st.session_state.config['mem_channels'],
            key='mem_channels', on_change=sync_widget, args=('mem_channels',)
        )
        st.number_input(
            'Memory Ranks per Channel (`--mem-ranks`)',
            min_value=1, help="Number of memory ranks per channel.",
            value=st.session_state.config['mem_ranks'],
            key='mem_ranks', on_change=sync_widget, args=('mem_ranks',)
        )
        st.number_input(
            'Memory Channels Interleave (`--mem-channels-intlv`)',
            min_value=0, help="Memory channels interleave value.",
            value=st.session_state.config['mem_channels_intlv'],
            key='mem_channels_intlv', on_change=sync_widget, args=('mem_channels_intlv',)
        )

    with col3:
        st.subheader("Features & External Systems")
        st.checkbox(
            'Enable DRAM Powerdown (`--enable-dram-powerdown`)',
            help="Enable low-power states in DRAMInterface.",
            value=st.session_state.config['enable_dram_powerdown'],
            key='enable_dram_powerdown', on_change=sync_widget, args=('enable_dram_powerdown',)
        )
        st.checkbox(
            'Enable Memchecker (`--memchecker`)',
            help="Enable the memory checker.",
            value=st.session_state.config['memchecker'],
            key='memchecker', on_change=sync_widget, args=('memchecker',)
        )
        st.text_input(
            'External Memory System (`--external-memory-system`)',
            help="Use external ports of this port_type for caches.",
            value=st.session_state.config['external_memory_system'],
            key='external_memory_system', on_change=sync_widget, args=('external_memory_system',)
        )
        st.text_input(
            'TLM Memory (`--tlm-memory`)',
            help="Use external port for SystemC TLM cosimulation.",
            value=st.session_state.config['tlm_memory'],
            key='tlm_memory', on_change=sync_widget, args=('tlm_memory',)
        )

# ==============================================================================
# --- Cache Configuration ---
# ==============================================================================
with st.expander("Cache Configuration", expanded=False):
    col1, col2, col3 = st.columns(3)
    size_units = ["kB", "MB", "GB"]
    with col1:
        st.subheader("Enable Caches")
        st.checkbox('Enable Caches (`--caches`)', value=st.session_state.config['caches'], key='caches', on_change=sync_widget, args=('caches',))
        st.checkbox('Enable L2 Cache (`--l2cache`)', value=st.session_state.config['l2cache'], key='l2cache', on_change=sync_widget, args=('l2cache',))
        st.subheader("Cache Counts")
        st.number_input('Num L2 Caches (`--num-l2caches`)', min_value=1, value=st.session_state.config['num_l2caches'], key='num_l2caches', on_change=sync_widget, args=('num_l2caches',))
        st.number_input('Num L3 Caches (`--num-l3caches`)', min_value=0, value=st.session_state.config['num_l3caches'], key='num_l3caches', on_change=sync_widget, args=('num_l3caches',))
        st.subheader("Misc Cache")
        st.number_input('Cacheline Size (`--cacheline_size`)', min_value=16, step=16, value=st.session_state.config['cacheline_size'], key='cacheline_size', on_change=sync_widget, args=('cacheline_size',))
    with col2:
        st.subheader("Cache Sizes")
        composite_input("L1D Size", "l1d_size", size_units)
        composite_input("L1I Size", "l1i_size", size_units)
        composite_input("L2 Size", "l2_size", size_units)
        composite_input("L3 Size", "l3_size", size_units)
    with col3:
        st.subheader("Cache Associativity")
        st.number_input('L1D Assoc (`--l1d_assoc`)', min_value=1, value=st.session_state.config['l1d_assoc'], key='l1d_assoc', on_change=sync_widget, args=('l1d_assoc',))
        st.number_input('L1I Assoc (`--l1i_assoc`)', min_value=1, value=st.session_state.config['l1i_assoc'], key='l1i_assoc', on_change=sync_widget, args=('l1i_assoc',))
        st.number_input('L2 Assoc (`--l2_assoc`)', min_value=1, value=st.session_state.config['l2_assoc'], key='l2_assoc', on_change=sync_widget, args=('l2_assoc',))
        st.number_input('L3 Assoc (`--l3_assoc`)', min_value=1, value=st.session_state.config['l3_assoc'], key='l3_assoc', on_change=sync_widget, args=('l3_assoc',))

# ==============================================================================
# --- Ruby and Network Configuration ---
# ==============================================================================
with st.expander("Ruby and Network Configuration", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Network Type & Topology")
        st.selectbox("Network Type (`--network`)", ['simple', 'garnet'], index=['simple', 'garnet'].index(st.session_state.config['network']), key='network', on_change=update_network_and_topology)
        st.text_input("Topology (`--topology`)", value=st.session_state.config['topology'], key='topology', on_change=sync_widget, args=('topology',))
        st.number_input("Mesh Rows (`--mesh-rows`)", min_value=1, value=st.session_state.config['mesh_rows'], key='mesh_rows', on_change=sync_widget, args=('mesh_rows',))
        st.subheader("Ruby System")
        st.checkbox("Enable Ruby (`--ruby`)", value=st.session_state.config['ruby'], key='ruby', on_change=sync_widget, args=('ruby',))
        composite_input("Ruby Clock", "ruby_clock", ["kHz", "MHz", "GHz"])
        st.checkbox('Access Backing Store', value=st.session_state.config['access_backing_store'], key='access_backing_store', on_change=sync_widget, args=('access_backing_store',))
        st.number_input(
            'Number of Directories (`--num-dirs`)',
            min_value=1,
            value=st.session_state.config['num_dirs'],
            key='num_dirs',
            on_change=sync_widget,
            args=('num_dirs',),
            help="Number of memory directories. Can be set independently of CPUs."
        )
        st.number_input('Recycle Latency (`--recycle-latency`)', min_value=0, value=st.session_state.config['recycle_latency'], key='recycle_latency', on_change=sync_widget, args=('recycle_latency',))
    with col2:
        st.subheader("Network Internals")
        st.number_input("Router Latency (`--router-latency`)", min_value=1, value=st.session_state.config['router_latency'], key='router_latency', on_change=sync_widget, args=('router_latency',))
        st.number_input("Link Latency (`--link-latency`)", min_value=1, value=st.session_state.config['link_latency'], key='link_latency', on_change=sync_widget, args=('link_latency',))
        st.number_input("Link Width (bits) (`--link-width-bits`)", min_value=8, step=8, value=st.session_state.config['link_width_bits'], key='link_width_bits', on_change=sync_widget, args=('link_width_bits',))
        st.number_input("VCs per VNet (`--vcs-per-vnet`)", min_value=1, value=st.session_state.config['vcs_per_vnet'], key='vcs_per_vnet', on_change=sync_widget, args=('vcs_per_vnet',))
        st.number_input("Garnet Deadlock Threshold", min_value=1, value=st.session_state.config['garnet_deadlock_threshold'], key='garnet_deadlock_threshold', on_change=sync_widget, args=('garnet_deadlock_threshold',))
    with col3:
        st.subheader("Routing & NUMA")
        st.selectbox("Routing Algorithm", options=[0, 1, 2], index=st.session_state.config['routing_algorithm'], format_func=lambda x: {0: "0: Weight-based", 1: "1: XY", 2: "2: Custom"}[x], key='routing_algorithm', on_change=sync_widget, args=('routing_algorithm',))
        st.checkbox("Enable Network Fault Model", value=st.session_state.config['network_fault_model'], key='network_fault_model', on_change=sync_widget, args=('network_fault_model',))
        st.checkbox("Enable Garnet Tracer", help="Enable the Garnet tracer.", value=st.session_state.config['garnet_tracer'], key='garnet_tracer', on_change=sync_widget, args=('garnet_tracer',))
        st.number_input("NUMA High Bit", min_value=0, value=st.session_state.config['numa_high_bit'], key='numa_high_bit', on_change=sync_widget, args=('numa_high_bit',))
        st.number_input("Interleaving Bits", min_value=0, value=st.session_state.config['interleaving_bits'], key='interleaving_bits', on_change=sync_widget, args=('interleaving_bits',))
        st.number_input("XOR Low Bit", min_value=0, value=st.session_state.config['xor_low_bit'], key='xor_low_bit', on_change=sync_widget, args=('xor_low_bit',))
        st.number_input("Ports", min_value=1, value=st.session_state.config['ports'], key='ports', on_change=sync_widget, args=('ports',))
    # In the "Ruby and Network Configuration" expander, after all the widgets...    

# ==============================================================================
# --- Traffic Injection Configuration ---
# ==============================================================================
with st.expander("Synthetic Traffic Injection", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Traffic Type")
        synthetic_options = ['uniform_random', 'tornado', 'bit_complement', 'bit_reverse', 'bit_rotation', 'neighbor', 'shuffle', 'transpose']
        st.selectbox("Synthetic Traffic Type (`--synthetic`)", synthetic_options, index=synthetic_options.index(st.session_state.config['synthetic']), key='synthetic', on_change=sync_widget, args=('synthetic',))
        st.selectbox("Injection VNet (`--inj-vnet`)", options=[-1, 0, 1, 2], index=[-1,0,1,2].index(st.session_state.config['inj_vnet']), format_func=lambda x: f"Random" if x == -1 else f"{x}", key='inj_vnet', on_change=sync_widget, args=('inj_vnet',))
    with col2:
        st.subheader("Injection Rate")
        st.number_input("Precision (`--precision`)", min_value=1, value=st.session_state.config['precision'], key='precision', on_change=sync_widget, args=('precision',))
        st.slider(
            "Injection Rate (`--injectionrate`)",
            min_value=0.0, max_value=1.0,
            value=st.session_state.config['injectionrate'],
            step=10**-st.session_state.config['precision'],
            help="Injection rate in packets per cycle per node.",
            key='injectionrate',
            on_change=sync_widget,
            args=('injectionrate',)
        )
    with col3:
        st.subheader("Injection Control")
        st.number_input("Max Packets to Inject", help="Stop injecting after this many packets. -1 to disable.", value=st.session_state.config['num_packets_max'], key='num_packets_max', on_change=sync_widget, args=('num_packets_max',))
        st.number_input("Single Sender ID", help="Only inject from this sender. -1 to disable.", value=st.session_state.config['single_sender_id'], key='single_sender_id', on_change=sync_widget, args=('single_sender_id',))
        st.number_input("Single Destination ID", help="Only send to this destination. -1 to disable.", value=st.session_state.config['single_dest_id'], key='single_dest_id', on_change=sync_widget, args=('single_dest_id',))

# ==============================================================================
# --- Generated Command and Config Summary ---
# ==============================================================================
st.header("Generated Command & Configuration")

command = generate_command_string(st.session_state.config, DEFAULTS)
st.subheader("Generated Command")
st.code(command, language="bash")

if st.session_state.config['network'] == 'garnet':
        st.markdown("---")
        st.subheader("Garnet Configuration")
        
        # Get current values
        cpus = st.session_state.config['num_cpus']
        rows = st.session_state.config['mesh_rows']
        
        # Check for validity
        if cpus % rows == 0:
            cols = cpus // rows
            st.info(
                f"✅ **Valid Configuration**: With **{cpus}** CPUs and **{rows}** mesh rows, "
                f"the script will create a **{rows} x {cols}** mesh network."
            )
        else:
            st.error(
                f"⚠️ **Invalid Configuration**: The number of CPUs ({cpus}) must be "
                f"perfectly divisible by the number of mesh rows ({rows})."
            )

# ==============================================================================
# --- Command Execution ---
# ==============================================================================
st.markdown("---")
st.subheader("Execute Command")

exec_col1, exec_col2, exec_col3 = st.columns([2, 2, 1])
with exec_col1:
    st.text_input("gem5 Executable Path", value=st.session_state.config['gem5_path'], key='gem5_path', on_change=sync_widget, args=('gem5_path',), help="Path to the gem5 executable (e.g., ./build/X86/gem5.opt)")
with exec_col2:
    st.text_input("Script Path", value=st.session_state.config['script_path'], key='script_path', on_change=sync_widget, args=('script_path',), help="Path to the python configuration script to run.")
with exec_col3:
    st.write("") 
    button_label = "Running..." if st.session_state.is_running else "Run Command"
    if st.button(button_label, disabled=st.session_state.is_running, width='stretch'):
        st.session_state.run_triggered = True
        st.rerun()

# --- Execution Logic (Triggered by Button) ---
if st.session_state.run_triggered:
    st.session_state.run_triggered = False
    st.session_state.last_run_messages = [] 
    st.session_state.is_running = True
    st.session_state.command_output = None
    st.session_state.command_error = None
    
    command_list = shlex.split(command)
    try:
        with st.spinner('🚀 Executing gem5 simulation... Please wait.'):
            result = subprocess.run(command_list, capture_output=True, text=True, check=False)
            time.sleep(1) 
        
        st.session_state.command_output = result.stdout
        st.session_state.command_error = result.stderr
        
        if result.returncode == 0:
            st.session_state.last_run_messages.append(("success", "✅ Command executed successfully!"))
            with st.spinner("💾 Parsing and saving statistics..."):
                parsed_stats = parse_stats_file() 
                if parsed_stats:
                    run_name = save_run_data(st.session_state.config, parsed_stats)
                    st.session_state.last_run_messages.append(("info", f"📈 Statistics saved to '{run_name}'!"))
                else:
                    st.session_state.last_run_messages.append(("warning", "⚠️ Could not find or parse stats.txt. No data was saved."))
                time.sleep(1)
        else:
            st.session_state.last_run_messages.append(("error", f"❌ Command failed with return code: {result.returncode}"))
    except FileNotFoundError:
        st.session_state.last_run_messages.append(("error", f"Command failed. The executable '{command_list[0]}' was not found."))
        st.session_state.command_error = f"Could not find the executable: {command_list[0]}"
    except Exception as e:
        st.session_state.last_run_messages.append(("error", f"An unexpected error occurred: {e}"))
        st.session_state.command_error = str(e)
    finally:
        st.session_state.is_running = False
        st.rerun()


# --- Persistent Display of Run Results ---
if st.session_state.last_run_messages:
    st.markdown("---")
    st.subheader("Last Run Status")
    for msg_type, msg_text in st.session_state.last_run_messages:
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "info":
            st.info(msg_text)
        elif msg_type == "warning":
            st.warning(msg_text)
        elif msg_type == "error":
            st.error(msg_text)

if st.session_state.command_output is not None:
    with st.expander("Standard Output", expanded=True):
        st.code(st.session_state.command_output, language="text")

if st.session_state.command_error:
    with st.expander("Standard Error", expanded=True):
        st.code(st.session_state.command_error, language="text")

# --- Full Configuration Viewer ---
with st.expander("View Full Configuration JSON"):
    st.json(st.session_state.config)