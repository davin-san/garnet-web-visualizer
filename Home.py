import streamlit as st

st.set_page_config(layout="centered")
st.title('Garnet Web Visualizer')

st.markdown(
    """
Welcome to the **Garnet Web Visualizer**, a browser-based front-end for running and analyzing  
**gem5's Garnet Network-on-Chip (NoC) simulations**.  

This tool organizes the workflow into three main sections:

- **System Configuration Adjuster**  
  Configure CPUs, memory, cache, Ruby/NoC settings, and synthetic traffic injection.  
  An auto-generated gem5 command is shown so you know exactly how your run is set up.  

- **Experiment Runner**  
  Sweep an independent variable (e.g., injection rate), set parameter values, and launch multiple simulations.  
  Results are stored in structured directories for easy comparison.  

- **JSON Data Analyzer**  
  Import completed run outputs, select statistics (latency, throughput, utilization),  
  and visualize trends across experiments with plots and tables.  

---

### 🚀 Quick Start
1. Go to **System Configuration Adjuster** and set your simulation parameters.  
   - Example: 16 CPUs, Mesh_XY topology, 4 mesh rows, injection rate 0.01.  
2. Review the **Generated Command** section at the bottom to see the exact gem5 command.  
3. Click **Run** to start the simulation.  
   - Logs and statistics are saved automatically under `run_data/<timestamp>`.  
4. For sweeps, open the **Experiment Runner** to test multiple injection rates or configurations.  
5. Use the **Visualize** tab to load JSON results and plot selected statistics.  

---

By combining configuration, experiment management, and visualization in one interface,  
this tool makes Garnet simulations **faster, reproducible, and more accessible** — without needing to manage command-line scripts manually.
"""
)
