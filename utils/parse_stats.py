import re
import json
import os
from datetime import datetime

# FIX: This regex now correctly parses lines regardless of the comment format.
# It looks for a key followed by a number/nan/inf, and ignores the rest of the line.
STAT_REGEX = re.compile(
    r"([a-zA-Z0-9_:\.\-]+)\s+([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|nan|inf)"
)

def parse_stats_file(filepath="m5out/stats.txt"):
    """
    Parses a gem5 stats.txt file, extracting a curated list of important, 
    common latency-related stats.

    Args:
        filepath (str): The path to the stats.txt file.

    Returns:
        dict: A dictionary containing the parsed latency statistics.
    """
    stats = {}
    if not os.path.exists(filepath):
        print(f"Warning: Stats file not found at {filepath}")
        return stats

    exact_latency_keys = {
        "simSeconds",
        "hostSeconds",
        "system.ruby.network.average_flit_latency",
        "system.ruby.network.average_flit_network_latency",
        "system.ruby.network.average_flit_queueing_latency",
        "system.ruby.network.average_packet_latency",
        "system.ruby.network.average_packet_network_latency",
        "system.ruby.network.average_packet_queueing_latency",
    }

    mem_ctrl_latency_suffixes = []

    with open(filepath, 'r') as f:
        for line in f:
            # Using .match() is slightly more efficient as we expect stats at the start of a line
            match = STAT_REGEX.match(line)
            if match:
                key = match.group(1).strip()
                is_target_stat = False

                if key in exact_latency_keys:
                    is_target_stat = True
                elif key.startswith("system.mem_ctrls"):
                    if any(key.endswith(suffix) for suffix in mem_ctrl_latency_suffixes):
                        is_target_stat = True

                if is_target_stat:
                    value_str = match.group(2)
                    try:
                        value = float(value_str)
                    except ValueError:
                        value = value_str # Keep 'nan', 'inf' as strings
                    stats[key] = value
    return stats

# --- Example Usage (no changes needed below this line) ---
def save_run_data(config, stats, output_dir="run_data"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_name = f"run_{timestamp}"
    run_data = {"run_name": run_name, "timestamp": timestamp, "config": config, "stats": stats}
    file_path = os.path.join(output_dir, f"{run_name}.json")
    with open(file_path, 'w') as f:
        json.dump(run_data, f, indent=4)
    print(f"Successfully saved run data to {file_path}")
    return run_name