import streamlit as st

st.title('Garnet Web Visualizer')

st.markdown(
    """
Welcome to the **Garnet Web Visualizer**, an interactive front-end for running and analyzing  
**gem5’s Garnet Network-on-Chip (NoC) simulations**.  

This tool streamlines the simulation process by providing an intuitive browser-based interface where you can:

- **Adjust system parameters** (CPU count, memory, cache, network topology, mesh size, and synthetic traffic injection)  
- **Automatically generate a gem5 command** based on your selections  
- **Run Garnet simulations directly** without typing long command lines  
- **Monitor execution logs** and view organized results for each run  
- **Visualize simulation statistics** such as latency, throughput, and utilization from gem5’s `stats.txt`  

All results are saved in structured output directories (`results/<run_id>`), including logs, configuration info, and statistics.  
This ensures each run is easy to reproduce, compare, and analyze.  

---

### 🚀 Quick Start
1. Open the **System Configuration Adjuster** panels and select your simulation parameters.  
   - Example: 16 CPUs, Mesh_XY topology, 4 mesh rows, uniform random traffic, injection rate 0.01.  
2. Review the **Generated Command** section at the bottom of the page.  
   - The gem5 command is auto-generated based on your inputs.  
3. Click **Run Command** to launch the simulation.  
   - gem5 runs in the background, and logs are captured automatically.  
4. Navigate to the **Dashboard** tab to analyze results.  
   - Graphs and tables make it easy to compare injection rate vs. latency, throughput, and more.  

---

This workflow removes the friction of manual configuration and command-line execution,  
making Garnet experiments **faster, more reproducible, and accessible** directly from your browser.
"""
)
