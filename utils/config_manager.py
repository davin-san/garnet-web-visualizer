import streamlit as st
import re
import os

class ConfigManager:
    """A class to manage gem5 configuration, UI widgets, and command generation."""

    DEFAULTS = {
        # App config
        'gem5_path': '../gem5-tracer/build/NULL/gem5.debug',
        'script_path': '../gem5-tracer/configs/example/garnet_synth_traffic.py',
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
        'mem_ranks': 2,
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
        'num_dirs': 16,
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

    def __init__(self, session_state_key: str):
        """
        Initializes the ConfigManager.
        Args:
            session_state_key (str): The key to use for storing config in st.session_state.
        """
        self.key = session_state_key
        if self.key not in st.session_state:
            st.session_state[self.key] = self.DEFAULTS.copy()
            st.session_state[self.key]['num_dirs'] = st.session_state[self.key]['num_cpus']
        
        # State for the file uploader logic
        if f'last_uploaded_id_{self.key}' not in st.session_state:
            st.session_state[f'last_uploaded_id_{self.key}'] = None 
    
    @property
    def config(self):
        """Property to easily access the config dictionary in session state."""
        return st.session_state[self.key]

    # --- Callbacks as Methods ---
    def sync_widget(self, config_key):
        if config_key in st.session_state:
            self.config[config_key] = st.session_state[config_key]

    def _sync_composite_widget(self, config_key, val_key, unit_key):
        value = st.session_state.get(val_key, 0)
        unit = st.session_state.get(unit_key, '')
        self.config[config_key] = f"{value}{unit}"
    
    def handle_cpu_change(self):
        new_cpu_val = st.session_state['num_cpus']
        self.config['num_cpus'] = new_cpu_val
        self.config['num_dirs'] = new_cpu_val
        st.session_state['num_dirs'] = new_cpu_val

        if self.config.get('network') == 'garnet':
            new_mesh_rows = int(new_cpu_val ** 0.5)
            while new_cpu_val % new_mesh_rows != 0:
                new_mesh_rows -= 1
                if new_mesh_rows == 0:
                    new_mesh_rows = 1
                    break
            self.config['mesh_rows'] = new_mesh_rows
            st.session_state['mesh_rows'] = new_mesh_rows

    def update_network_and_topology(self):
        new_network_val = st.session_state.network
        self.config['network'] = new_network_val

        if new_network_val == 'garnet':
            new_topology = 'Mesh_XY'
        elif new_network_val == 'simple':
            new_topology = 'Crossbar'
        # In case there are other network types in the future
        else:
            new_topology = self.config.get('topology', 'Crossbar')

        self.config['topology'] = new_topology
        st.session_state['topology'] = new_topology

    # --- UI Rendering Methods ---
    def composite_input(self, label, config_key, units, help_text=""):
        st.markdown(f"**{label}** (`--{config_key.replace('_','-')}`)")
        value_str = str(self.config[config_key]).strip()
        match = re.match(r"([0-9.]+)\s*([a-zA-Z]+)", value_str)
        if match:
            val, unit = match.groups()
            try:
                default_val = float(val)
            except ValueError:
                default_val = 0.0
            default_unit = unit
        else:
            default_val = 0.0
            default_unit = units[0]
        
        val_key = f"{config_key}_val_widget"
        unit_key = f"{config_key}_unit_widget"

        col1, col2 = st.columns([2, 1])
        col1.number_input(label, value=default_val, key=val_key, on_change=self._sync_composite_widget, args=(config_key, val_key, unit_key), label_visibility="collapsed", step=1.0, format="%.2f")
        col2.selectbox(label + " unit", options=units, index=units.index(default_unit) if default_unit in units else 0, key=unit_key, on_change=self._sync_composite_widget, args=(config_key, val_key, unit_key), label_visibility="collapsed")
        if help_text:
            st.caption(help_text)

    def display_widgets(self, exclude_key: str):
        """Renders all configuration widgets, skipping any key in the exclude list."""
        
        # Helper function to check if a widget should be displayed
        def should_display(key):
            return key != exclude_key

        with st.expander("System, CPU, and Simulation Control", expanded=True):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.subheader("CPU & System")
                if should_display('num_cpus'):
                    st.number_input(
                        'Number of CPUs (`--num-cpus`)',
                        min_value=1,
                        step=1,
                        help="Number of CPUs to simulate. When using the Garnet network, this will also auto-update mesh-rows to a valid value.",
                        value=self.config['num_cpus'],
                        key='num_cpus',
                        on_change=self.handle_cpu_change
                    )

                if should_display('sys_voltage'):
                    st.text_input(
                        'System Voltage (`--sys-voltage`)',
                        help="Top-level voltage for blocks running at system power supply (e.g., '1.0V').",
                        value=self.config['sys_voltage'],
                        key='sys_voltage',
                        on_change=self.sync_widget,
                        args=('sys_voltage',)
                    )
                
                if should_display('sys_clock'):
                    self.composite_input("System Clock", "sys_clock", ["kHz", "MHz", "GHz"], help_text="Top-level clock for blocks running at system frequency.")

            with col2:
                st.subheader("Simulation Time")
                if should_display('abs_max_tick'):
                    st.number_input(
                        'Absolute Max Tick (`--abs-max-tick`)',
                        min_value=0,
                        step=1000,
                        help="Run to absolute simulated tick specified.",
                        value=self.config['abs_max_tick'],
                        key='abs_max_tick',
                        on_change=self.sync_widget,
                        args=('abs_max_tick',)
                    )
                if should_display('rel_max_tick'):
                    st.number_input(
                        'Relative Max Tick (`--rel-max-tick`)',
                        min_value=0,
                        step=1000,
                        help="Simulate for a specified number of ticks relative to the start tick.",
                        value=self.config['rel_max_tick'],
                        key='rel_max_tick',
                        on_change=self.sync_widget,
                        args=('rel_max_tick',)
                    )
                if should_display('maxtime'):
                    st.number_input(
                        'Max Time (seconds) (`--maxtime`)',
                        min_value=0.0,
                        format="%.4f",
                        help="Run to the specified absolute simulated time in seconds.",
                        value=self.config['maxtime'],
                        key='maxtime',
                        on_change=self.sync_widget,
                        args=('maxtime',)
                    )
                if should_display('sim_cycles'):
                    st.number_input(
                        'Simulation Cycles (`--sim-cycles`)',
                        min_value=0,
                        help="Number of simulation cycles to run.",
                        value=self.config['sim_cycles'],
                        key='sim_cycles',
                        on_change=self.sync_widget,
                        args=('sim_cycles',)
                    )

            with col3:
                if should_display('param'):
                    st.subheader("SimObject Parameters")
                    st.text_area(
                        "Set Parameter (`--param`)",
                        height=200,
                        help="Set a SimObject parameter, e.g., 'system.cpu[0].max_insts_all_threads = 42'",
                        value=self.config['param'],
                        key='param',
                        on_change=self.sync_widget,
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
                if should_display('mem_type'):
                    st.selectbox(
                        'Memory Type (`--mem-type`)',
                        options=mem_types_list,
                        index=mem_types_list.index(self.config['mem_type']) if self.config['mem_type'] in mem_types_list else 0,
                        help="Type of memory to use.",
                        key='mem_type',
                        on_change=self.sync_widget,
                        args=('mem_type',)
                    )
                if should_display('mem_size'):
                    self.composite_input("Memory Size", "mem_size", ["kB", "MB", "GB", "TB"], help_text="Total memory size.")

            with col2:
                st.subheader("Channels & Ranks")
                if should_display('mem_channels'):
                    st.number_input(
                        'Memory Channels (`--mem-channels`)',
                        min_value=1, help="Number of memory channels.",
                        value=self.config['mem_channels'],
                        key='mem_channels', on_change=self.sync_widget, args=('mem_channels',)
                    )
                if should_display('mem_ranks'):
                    st.number_input(
                        'Memory Ranks per Channel (`--mem-ranks`)',
                        min_value=1, help="Number of memory ranks per channel.",
                        value=self.config['mem_ranks'],
                        key='mem_ranks', on_change=self.sync_widget, args=('mem_ranks',)
                    )
                if should_display('mem_channels_intlv'):
                    st.number_input(
                        'Memory Channels Interleave (`--mem-channels-intlv`)',
                        min_value=0, help="Memory channels interleave value.",
                        value=self.config['mem_channels_intlv'],
                        key='mem_channels_intlv', on_change=self.sync_widget, args=('mem_channels_intlv',)
                    )

            with col3:
                st.subheader("Features & External Systems")
                if should_display('enable_dram_powerdown'):
                    st.checkbox(
                        'Enable DRAM Powerdown (`--enable-dram-powerdown`)',
                        help="Enable low-power states in DRAMInterface.",
                        value=self.config['enable_dram_powerdown'],
                        key='enable_dram_powerdown', on_change=self.sync_widget, args=('enable_dram_powerdown',)
                    )
                if should_display('memchecker'):
                    st.checkbox(
                        'Enable Memchecker (`--memchecker`)',
                        help="Enable the memory checker.",
                        value=self.config['memchecker'],
                        key='memchecker', on_change=self.sync_widget, args=('memchecker',)
                    )
                if should_display('external_memory_system'):
                    st.text_input(
                        'External Memory System (`--external-memory-system`)',
                        help="Use external ports of this port_type for caches.",
                        value=self.config['external_memory_system'],
                        key='external_memory_system', on_change=self.sync_widget, args=('external_memory_system',)
                    )
                if should_display('tlm_memory'):
                    st.text_input(
                        'TLM Memory (`--tlm-memory`)',
                        help="Use external port for SystemC TLM cosimulation.",
                        value=self.config['tlm_memory'],
                        key='tlm_memory', on_change=self.sync_widget, args=('tlm_memory',)
                    )

        # ==============================================================================
        # --- Cache Configuration ---
        # ==============================================================================
        with st.expander("Cache Configuration", expanded=False):
            col1, col2, col3 = st.columns(3)
            size_units = ["kB", "MB", "GB"]
            with col1:
                st.subheader("Enable Caches")
                if should_display('caches'):
                    st.checkbox('Enable Caches (`--caches`)', value=self.config['caches'], key='caches', on_change=self.sync_widget, args=('caches',))
                if should_display('l2cache'):
                    st.checkbox('Enable L2 Cache (`--l2cache`)', value=self.config['l2cache'], key='l2cache', on_change=self.sync_widget, args=('l2cache',))
                st.subheader("Cache Counts")
                if should_display('num_l2caches'):
                    st.number_input('Num L2 Caches (`--num-l2caches`)', min_value=1, value=self.config['num_l2caches'], key='num_l2caches', on_change=self.sync_widget, args=('num_l2caches',))
                if should_display('num_l3caches'):
                    st.number_input('Num L3 Caches (`--num-l3caches`)', min_value=0, value=self.config['num_l3caches'], key='num_l3caches', on_change=self.sync_widget, args=('num_l3caches',))
                st.subheader("Misc Cache")
                if should_display('cacheline_size'):
                    st.number_input('Cacheline Size (`--cacheline_size`)', min_value=16, step=16, value=self.config['cacheline_size'], key='cacheline_size', on_change=self.sync_widget, args=('cacheline_size',))
            with col2:
                st.subheader("Cache Sizes")
                if should_display('l1d_size'):
                    self.composite_input("L1D Size", "l1d_size", size_units)
                if should_display('l1i_size'):
                    self.composite_input("L1I Size", "l1i_size", size_units)
                if should_display('l2_size'):
                    self.composite_input("L2 Size", "l2_size", size_units)
                if should_display('l3_size'):
                    self.composite_input("L3 Size", "l3_size", size_units)
            with col3:
                st.subheader("Cache Associativity")
                if should_display('l1d_assoc'):
                    st.number_input('L1D Assoc (`--l1d_assoc`)', min_value=1, value=self.config['l1d_assoc'], key='l1d_assoc', on_change=self.sync_widget, args=('l1d_assoc',))
                if should_display('l1i_assoc'):
                    st.number_input('L1I Assoc (`--l1i_assoc`)', min_value=1, value=self.config['l1i_assoc'], key='l1i_assoc', on_change=self.sync_widget, args=('l1i_assoc',))
                if should_display('l2_assoc'):
                    st.number_input('L2 Assoc (`--l2_assoc`)', min_value=1, value=self.config['l2_assoc'], key='l2_assoc', on_change=self.sync_widget, args=('l2_assoc',))
                if should_display('l3_assoc'):
                    st.number_input('L3 Assoc (`--l3_assoc`)', min_value=1, value=self.config['l3_assoc'], key='l3_assoc', on_change=self.sync_widget, args=('l3_assoc',))

        # ==============================================================================
        # --- Ruby and Network Configuration ---
        # ==============================================================================
        with st.expander("Ruby and Network Configuration", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            custom_topology_dir = 'custom_topologies'
            if not os.path.exists(custom_topology_dir):
                os.makedirs(custom_topology_dir)
            custom_topologies = [f for f in os.listdir(custom_topology_dir) if f.endswith('.py')]
            
            topology_options = ['Crossbar', 'Mesh_XY'] + custom_topologies
            
            with col1:
                st.subheader("Network Type & Topology")
                if should_display('network'):
                    st.selectbox("Network Type (`--network`)", ['simple', 'garnet'], index=['simple', 'garnet'].index(self.config['network']), key='network', on_change=self.update_network_and_topology)
                
                if should_display('topology'):
                    st.selectbox("Topology (`--topology`)", topology_options, index=topology_options.index(self.config['topology']) if self.config['topology'] in topology_options else 0, key='topology', on_change=self.sync_widget, args=('topology',))
                
                    uploaded_file = st.file_uploader("Upload Custom Topology", type=['py'], key=f"uploader_{self.key}", accept_multiple_files=False)
                    if uploaded_file and uploaded_file.file_id != st.session_state[f'last_uploaded_id_{self.key}']:
                        # Define the path and save the file
                        file_path = os.path.join('custom_topologies', uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        # Update the session state to prevent re-uploading
                        st.session_state[f'last_uploaded_id_{self.key}'] = uploaded_file.file_id
                        st.rerun()

                if should_display('mesh_rows'):
                    st.number_input("Mesh Rows (`--mesh-rows`)", min_value=1, value=self.config['mesh_rows'], key='mesh_rows', on_change=self.sync_widget, args=('mesh_rows',))
                
                st.subheader("Ruby System")
                if should_display('ruby'):
                    st.checkbox("Enable Ruby (`--ruby`)", value=self.config['ruby'], key='ruby', on_change=self.sync_widget, args=('ruby',))
                if should_display('ruby_clock'):
                    self.composite_input("Ruby Clock", "ruby_clock", ["kHz", "MHz", "GHz"])
                if should_display('access_backing_store'):
                    st.checkbox('Access Backing Store', value=self.config['access_backing_store'], key='access_backing_store', on_change=self.sync_widget, args=('access_backing_store',))
                if should_display('num_dirs'):
                    st.number_input(
                        'Number of Directories (`--num-dirs`)',
                        min_value=1,
                        value=self.config['num_dirs'],
                        key='num_dirs',
                        on_change=self.sync_widget,
                        args=('num_dirs',),
                        help="Number of memory directories. Can be set independently of CPUs."
                    )
                if should_display('recycle_latency'):
                    st.number_input('Recycle Latency (`--recycle-latency`)', min_value=0, value=self.config['recycle_latency'], key='recycle_latency', on_change=self.sync_widget, args=('recycle_latency',))
            
            with col2:
                st.subheader("Network Internals")
                if should_display('router_latency'):
                    st.number_input("Router Latency (`--router-latency`)", min_value=1, value=self.config['router_latency'], key='router_latency', on_change=self.sync_widget, args=('router_latency',))
                if should_display('link_latency'):
                    st.number_input("Link Latency (`--link-latency`)", min_value=1, value=self.config['link_latency'], key='link_latency', on_change=self.sync_widget, args=('link_latency',))
                if should_display('link_width_bits'):
                    st.number_input("Link Width (bits) (`--link-width-bits`)", min_value=8, step=8, value=self.config['link_width_bits'], key='link_width_bits', on_change=self.sync_widget, args=('link_width_bits',))
                if should_display('vcs_per_vnet'):
                    st.number_input("VCs per VNet (`--vcs-per-vnet`)", min_value=1, value=self.config['vcs_per_vnet'], key='vcs_per_vnet', on_change=self.sync_widget, args=('vcs_per_vnet',))
                if should_display('garnet_deadlock_threshold'):
                    st.number_input("Garnet Deadlock Threshold", min_value=1, value=self.config['garnet_deadlock_threshold'], key='garnet_deadlock_threshold', on_change=self.sync_widget, args=('garnet_deadlock_threshold',))
            
            with col3:
                st.subheader("Routing & NUMA")
                if should_display('routing_algorithm'):
                    st.selectbox("Routing Algorithm", options=[0, 1, 2], index=self.config['routing_algorithm'], format_func=lambda x: {0: "0: Weight-based", 1: "1: XY", 2: "2: Custom"}[x], key='routing_algorithm', on_change=self.sync_widget, args=('routing_algorithm',))
                if should_display('network_fault_model'):
                    st.checkbox("Enable Network Fault Model", value=self.config['network_fault_model'], key='network_fault_model', on_change=self.sync_widget, args=('network_fault_model',))
                if should_display('garnet_tracer'):
                    st.checkbox("Enable Garnet Tracer", help="Enable the Garnet tracer.", value=self.config['garnet_tracer'], key='garnet_tracer', on_change=self.sync_widget, args=('garnet_tracer',))
                if should_display('numa_high_bit'):
                    st.number_input("NUMA High Bit", min_value=0, value=self.config['numa_high_bit'], key='numa_high_bit', on_change=self.sync_widget, args=('numa_high_bit',))
                if should_display('interleaving_bits'):
                    st.number_input("Interleaving Bits", min_value=0, value=self.config['interleaving_bits'], key='interleaving_bits', on_change=self.sync_widget, args=('interleaving_bits',))
                if should_display('xor_low_bit'):
                    st.number_input("XOR Low Bit", min_value=0, value=self.config['xor_low_bit'], key='xor_low_bit', on_change=self.sync_widget, args=('xor_low_bit',))
                if should_display('ports'):
                    st.number_input("Ports", min_value=1, value=self.config['ports'], key='ports', on_change=self.sync_widget, args=('ports',))
            
        # ==============================================================================
        # --- Traffic Injection Configuration ---
        # ==============================================================================
        with st.expander("Synthetic Traffic Injection", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.subheader("Traffic Type")
                synthetic_options = ['uniform_random', 'tornado', 'bit_complement', 'bit_reverse', 'bit_rotation', 'neighbor', 'shuffle', 'transpose']
                if should_display('synthetic'):
                    st.selectbox("Synthetic Traffic Type (`--synthetic`)", synthetic_options, index=synthetic_options.index(self.config['synthetic']), key='synthetic', on_change=self.sync_widget, args=('synthetic',))
                if should_display('inj_vnet'):
                    st.selectbox("Injection VNet (`--inj-vnet`)", options=[-1, 0, 1, 2], index=[-1,0,1,2].index(self.config['inj_vnet']), format_func=lambda x: f"Random" if x == -1 else f"{x}", key='inj_vnet', on_change=self.sync_widget, args=('inj_vnet',))
            
            with col2:
                st.subheader("Injection Rate")
                if should_display('precision'):
                    st.number_input("Precision (`--precision`)", min_value=1, value=self.config['precision'], key='precision', on_change=self.sync_widget, args=('precision',))
                if should_display('injectionrate'):
                    st.slider(
                        "Injection Rate (`--injectionrate`)",
                        min_value=0.0, max_value=1.0,
                        value=self.config['injectionrate'],
                        step=10**-self.config['precision'],
                        help="Injection rate in packets per cycle per node.",
                        key='injectionrate',
                        on_change=self.sync_widget,
                        args=('injectionrate',)
                    )
            
            with col3:
                st.subheader("Injection Control")
                if should_display('num_packets_max'):
                    st.number_input("Max Packets to Inject", help="Stop injecting after this many packets. -1 to disable.", value=self.config['num_packets_max'], key='num_packets_max', on_change=self.sync_widget, args=('num_packets_max',))
                if should_display('single_sender_id'):
                    st.number_input("Single Sender ID", help="Only inject from this sender. -1 to disable.", value=self.config['single_sender_id'], key='single_sender_id', on_change=self.sync_widget, args=('single_sender_id',))
                if should_display('single_dest_id'):
                    st.number_input("Single Destination ID", help="Only send to this destination. -1 to disable.", value=self.config['single_dest_id'], key='single_dest_id', on_change=self.sync_widget, args=('single_dest_id',))

        if st.session_state['network'] == 'garnet':
            # Get current values
            cpus = st.session_state['num_cpus']
            rows = st.session_state['mesh_rows']
            
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

    def generate_command_string(self):
        """Generates the command string from the current configuration."""
        config = self.config
        executable_path = config.get('gem5_path', self.DEFAULTS['gem5_path'])
        script_path = config.get('script_path', self.DEFAULTS['script_path'])
        base_cmd = f"{executable_path} {script_path}"
        args = []

        is_garnet_active = config.get('network') == 'garnet'
        required_garnet_keys = ['num_cpus', 'num_dirs', 'mesh_rows']
        
        for key, value in config.items():
            if key in ['gem5_path', 'script_path']:
                continue

            if key == 'num_dirs' and value == config.get('num_cpus') and not is_garnet_active:
                continue

            default_value = self.DEFAULTS.get(key)
            if value == default_value and not (is_garnet_active and key in required_garnet_keys):
                continue
                
            flag = f"--{key.replace('_', '-')}"
            
            if isinstance(value, bool):
                if value:
                    args.append(flag)
            else:
                if key == 'topology' and str(value).endswith('.py'):
                    args.append(f"{flag}=custom_topologies/{value}")
                else:
                    args.append(f"{flag}={value}")
        
        return f"{base_cmd} {' '.join(args)}"