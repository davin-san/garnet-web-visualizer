import streamlit as st
import os
import plotly.graph_objects as go
from collections import defaultdict
import struct  # For binary unpacking
import utils.garnet_event_pb2

# ========== Configuration ==========
LOG_FILE_PATH = "traces/garnet_event_log.bin"
MESH_DIMENSION = 4
ANIMATION_INTERVAL = 250

# ========== Step 1. Parse garnet_event_log.bin with flit tracking ==========
# Use Streamlit's caching to avoid re-parsing the large log file on every interaction
@st.cache_data
def parse_log(filename):
    """
    Parse the binary Protobuf log and track which flits are currently at
    each router/link at each tick.
    Strategy: Build complete state at each tick by tracking flit movements.
    """
    
    # Note: We removed the os.path.join(script_dir, filename) logic
    # The filename passed in is now the absolute path.

    # Track current location of each flit (global_id -> location info)
    flit_locations = {}
    
    # Read and parse all events from the Protobuf file
    events = []
    try:
        with open(filename, "rb") as f:
            while True:
                # Read the 4-byte length prefix
                len_bytes = f.read(4)
                if not len_bytes:
                    break  # End of file
                
                # Unpack the length (little-endian unsigned int)
                try:
                    msg_len = struct.unpack('<I', len_bytes)[0]
                except struct.error as e:
                    st.error(f"Error unpacking message length: {e}. File may be corrupt.")
                    return {}
                    
                # Read the actual message bytes
                msg_bytes = f.read(msg_len)
                if len(msg_bytes) != msg_len:
                    st.warning(f"Error: Expected {msg_len} bytes, got {len(msg_bytes)}. Truncated file.")
                    break
                
                # Deserialize the Protobuf message
                event_pb = utils.garnet_event_pb2.GarnetEvent()
                try:
                    event_pb.ParseFromString(msg_bytes)
                except Exception as e:
                    st.warning(f"Error parsing protobuf message: {e}")
                    continue
                
                # Store event data in a dictionary, similar to the old parser
                evt_data = {
                    'tick': event_pb.tick,
                    'event': event_pb.status,
                    'global_id': event_pb.global_id,
                    'pack_id': event_pb.packet_id,
                    'flit_id': event_pb.id,
                }
                
                # Add event-specific data based on the Protobuf fields
                if evt_data['event'] == 'RI':
                    evt_data['src'] = event_pb.src
                    evt_data['dest'] = event_pb.dest
                elif evt_data['event'] in ('SI', 'RR', 'ST', 'DT'):
                    # This one field (link_id) is used for router_id,
                    # ext_link_id, and int_link_id
                    evt_data['location_id'] = event_pb.link_id
                # 'SE' event needs no extra data
                
                events.append(evt_data)

    except FileNotFoundError:
        st.error(f"Error: Log file not found at {filename}")
        return {}
    except Exception as e:
        st.error(f"An error occurred reading the log file: {e}")
        return {}
        
    # Sort by tick
    events.sort(key=lambda x: x['tick'])
    
    # Track state changes
    tick_states = {}  # tick -> state snapshot
    
    for evt in events:
        tick = evt['tick']
        event = evt['event']
        global_id = evt['global_id']
        pack_id = evt['pack_id']
        flit_id = evt['flit_id']
        
        # Initialize flit info on first encounter (RI event)
        if event == 'RI':
            src = evt['src']
            dest = evt['dest']
            flit_locations[global_id] = {
                'src': src,
                'dest': dest,
                'pack_id': pack_id,
                'flit_id': flit_id,
                'location_type': None,
                'location_id': None
            }
        
        # Update flit location based on event
        if global_id in flit_locations:
            if event == 'SI':
                # Flit enters router from external link (injection)
                ext_link_id = evt['location_id']
                router_id = ext_link_id
                flit_locations[global_id]['location_type'] = 'router'
                flit_locations[global_id]['location_id'] = router_id
            
            elif event == 'RR':
                # Router receives flit
                router_id = evt['location_id']
                flit_locations[global_id]['location_type'] = 'router'
                flit_locations[global_id]['location_id'] = router_id
            
            elif event == 'ST':
                # Flit starts transmitting on internal link
                int_link_id = evt['location_id']
                flit_locations[global_id]['location_type'] = 'link'
                flit_locations[global_id]['location_id'] = int_link_id
            
            elif event == 'DT':
                # Flit during transmission (still on link)
                int_link_id = evt['location_id']
                flit_locations[global_id]['location_type'] = 'link'
                flit_locations[global_id]['location_id'] = int_link_id
            
            elif event == 'SE':
                # Flit ejects (leaves the network)
                flit_locations[global_id]['location_type'] = 'ejected'
                flit_locations[global_id]['location_id'] = None
        
        # Save state snapshot at this tick
        # Create snapshot of ALL active flits at this moment
        snapshot = {'routers': defaultdict(list), 'links': defaultdict(list)}
        
        for gid, loc in flit_locations.items():
            if loc['location_type'] == 'router' and loc['location_id'] is not None:
                router_id = loc['location_id']
                flit_info = {
                    'global_id': gid,
                    'src': loc['src'],
                    'dest': loc['dest'],
                    'pack_id': loc['pack_id'],
                    'flit_id': loc['flit_id']
                }
                snapshot['routers'][router_id].append(flit_info)
            
            elif loc['location_type'] == 'link' and loc['location_id'] is not None:
                link_id = loc['location_id']
                flit_info = {
                    'global_id': gid,
                    'src': loc['src'],
                    'dest': loc['dest'],
                    'pack_id': loc['pack_id'],
                    'flit_id': loc['flit_id']
                }
                snapshot['links'][link_id].append(flit_info)
        
        tick_states[tick] = snapshot
    
    return tick_states

# ========== Step 2. Build Mesh XY topology ==========
# Cache this simple function as well
@st.cache_data
def build_mesh_xy(n):
    """
    Return router positions + link mapping
    routers: {id: (x,y)}
    links: {lid: (src,dst)}
    """
    routers = {r: (r // n, r % n) for r in range(n*n)}
    links = {}
    lid = 0
    link_count=0
    # East output to West input links (weight = 1)
    for row in range(n):
        for col in range(n):
            if col + 1 < n:
                east_out = col + (row * n)
                west_in = (col + 1) + (row * n)
                links[link_count]=(east_out,west_in)
                link_count += 1

    # West output to East input links (weight = 1)
    for row in range(n):
        for col in range(n):
            if col + 1 < n:
                east_in = col + (row * n)
                west_out = (col + 1) + (row * n)
                links[link_count]=(west_out,east_in)
                link_count += 1

    # North output to South input links (weight = 2)
    for col in range(n):
        for row in range(n):
            if row + 1 < n:
                north_out = col + (row * n)
                south_in = col + ((row + 1) * n)
                links[link_count]=(north_out,south_in)
                link_count += 1

    # South output to North input links (weight = 2)
    for col in range(n):
        for row in range(n):
            if row + 1 < n:
                north_in = col + (row * n)
                south_out = col + ((row + 1) * n)
                links[link_count]=(south_out,north_in)
                link_count += 1

    return routers, links

# ========== Step 3. Generate Plotly animation ==========
def make_animation(snapshots, routers, links, interval=250):
    ticks_all = sorted(snapshots.keys())
    if not ticks_all:
        raise ValueError("No ticks found in snapshots! Check your log parsing.")

    # Group by interval
    max_tick = ticks_all[-1]
    ticks = list(range(0, max_tick+1, interval))

    frames = []

    for t in ticks:
        # Find most recent snapshot <= t
        available_ticks = [tk for tk in ticks_all if tk <= t]
        if available_ticks:
            snap = snapshots[available_ticks[-1]]
        else:
            snap = {"routers": defaultdict(list), "links": defaultdict(list)}

        # ----- Routers -----
        xs = [routers[r][0] for r in routers]
        ys = [routers[r][1] for r in routers]
        sizes = [len(snap["routers"].get(r, []))*5+10 for r in routers]
        colors = ["green" if len(snap["routers"].get(r, [])) > 0 else "steelblue" for r in routers]
        
        hover_texts = []
        for r in routers:
            flits = snap["routers"].get(r, [])
            if flits:
                flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                                for f in flits]
                flit_info = "<br>".join(flit_lines)
                hover_texts.append(f"<b>Router {r}</b><br>Flits: {len(flits)}<br>{flit_info}")
            else:
                hover_texts.append(f"<b>Router {r}</b><br>No flits")

        # ----- Links -----
        link_traces = []
        for lid, (a, b) in links.items():
            x0, y0 = routers[a]
            x1, y1 = routers[b]
            
            # Get flits on this link
            flits = snap["links"].get(lid, [])
            if a > b:
                flits1 = snap["links"].get(lid-12,[]) # This logic seems specific, retained it
            else:
                flits1 = snap["links"].get(lid+12,[]) # This logic seems specific, retained it
            
            # Link hover text
            if flits:
                flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                                for f in flits]
                flit_info = "<br>".join(flit_lines)
                hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>Flits: {len(flits)}<br>{flit_info}"
            else:
                hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>No flits"
            
            # Link width based on flit count
            line_width = max(2, len(flits) * 2)
            
            flag = len(flits1) > 0 or len(flits) > 0
            
            line_color = "red" if flag else "lightgray"
            
            link_traces.append(
                go.Scatter(
                    x=[x0, x1], y=[y0, y1],
                    mode="lines",
                    line=dict(color=line_color, width=line_width),
                    text=hover_text,
                    hoverinfo="text",
                    showlegend=False
                )
            )

        frames.append(go.Frame(
            data=link_traces + [
                go.Scatter(x=xs, y=ys, mode="markers",
                           marker=dict(size=sizes, color=colors, 
                                       line=dict(width=2, color="darkblue")),
                           text=hover_texts,
                           hoverinfo="text",
                           showlegend=False),
            ],
            name=str(t)
        ))

    # Initial frame
    t0 = ticks[0]
    snap = snapshots.get(t0, {"routers": defaultdict(list), "links": defaultdict(list)})
    xs = [routers[r][0] for r in routers]
    ys = [routers[r][1] for r in routers]
    sizes = [len(snap["routers"].get(r, []))*5+10 for r in routers]
    
    hover_texts = []
    for r in routers:
        flits = snap["routers"].get(r, [])
        if flits:
            flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                            for f in flits]
            flit_info = "<br>".join(flit_lines)
            hover_texts.append(f"<b>Router {r}</b><br>Flits: {len(flits)}<br>{flit_info}")
        else:
            hover_texts.append(f"<b>Router {r}</b><br>No flits")

    # Initial links
    initial_link_traces = []
    for lid, (a, b) in links.items():
        x0, y0 = routers[a]
        x1, y1 = routers[b]
        
        flits = snap["links"].get(lid, [])
        
        if flits:
            flit_lines = [f"G{f['global_id']} (P{f['pack_id']}.F{f['flit_id']}): R{f['src']}→R{f['dest']}" 
                            for f in flits]
            flit_info = "<br>".join(flit_lines)
            hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>Flits: {len(flits)}<br>{flit_info}"
        else:
            hover_text = f"<b>Link {lid}</b> (R{a}→R{b})<br>No flits"
        
        line_width = max(2, len(flits) * 2)
        line_color = "red" if len(flits) > 0 else "lightgray"
        
        initial_link_traces.append(
            go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color=line_color, width=line_width),
                text=hover_text,
                hoverinfo="text",
                showlegend=False
            )
        )

    fig = go.Figure(
        data=initial_link_traces + [
            go.Scatter(x=xs, y=ys, mode="markers",
                       marker=dict(size=sizes, color="steelblue",
                                   line=dict(width=2, color="darkblue")),
                       text=hover_texts,
                       hoverinfo="text",
                       showlegend=False),
        ],
        layout=go.Layout(
            title=f"{MESH_DIMENSION}x{MESH_DIMENSION} Mesh Network Flit Tracker (Step: {interval} ticks)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
            hovermode='closest',
            plot_bgcolor='white',
            updatemenus=[{
                "buttons": [
                    {"args": [None, {"frame": {"duration": 500, "redraw": True},
                                     "fromcurrent": True}],
                     "label": "▶ Play",
                     "method": "animate"},
                    {"args": [[None], {"frame": {"duration": 0, "redraw": True},
                                      "mode": "immediate",
                                      "transition": {"duration": 0}}],
                     "label": "⏸ Pause",
                     "method": "animate"},
                ],
                "direction": "left",
                "pad": {"r": 10, "t": 87},
                "type": "buttons",
                "x": 0.1,
                "y": 1.15,
            }],
            sliders=[{
                "active": 0,
                "steps": [
                    {"args": [[str(t)], {"frame": {"duration": 0, "redraw": True},
                                         "mode": "immediate",
                                         "transition": {"duration": 0}}],
                     "label": f"T={t}",
                     "method": "animate"}
                    for t in ticks
                ],
                "x": 0.1,
                "len": 0.85,
                "xanchor": "left",
                "y": 0,
                "yanchor": "top",
            }]
        ),
        frames=frames
    )
    return fig

# ========== Main Streamlit App Logic ==========
def main():
    st.set_page_config(layout="wide", page_title="Garnet Flit Visualizer")
    st.title("Garnet Network-on-Chip Flit Visualizer")

    # Check if the log file exists
    if os.path.exists(LOG_FILE_PATH):
        st.success(f"Log file found: {LOG_FILE_PATH}")
        
        # Run the processing functions
        with st.spinner(f"Parsing log file... (This may take a moment)"):
            snapshots = parse_log(LOG_FILE_PATH)
        
        if not snapshots:
            st.error("Log file was found but no data could be parsed. Is the log file empty?")
            return

        st.info(f"Log file parsed. Found {len(snapshots)} tick snapshots.")

        routers, links = build_mesh_xy(MESH_DIMENSION)
        
        with st.spinner("Generating animation..."):
            fig = make_animation(snapshots, routers, links, interval=ANIMATION_INTERVAL)
        
        st.plotly_chart(fig, use_container_width=True)

    else:
        # File does not exist
        st.error(f"Log file not found.")
        st.info(f"The application is looking for the log file at this exact path: `{LOG_FILE_PATH}`")
        st.warning("Please ensure the simulation has run and produced the log file at the correct location.")

if __name__ == "__main__":
    main()
