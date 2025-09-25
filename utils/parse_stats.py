import json
import re
import os
from typing import Dict, Union
from datetime import datetime

# MODIFICATION: The regex now expects a single space, as we normalize the line first.
STAT_REGEX = re.compile(
    r"([a-zA-Z0-9_:\.\-]+) ([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|nan|inf)"
)

def parse_stats_file(filepath: str = "m5out/stats.txt") -> Dict[str, Union[float, str]]:
    """
    Parses a gem5 stats.txt file, extracting a curated list of important,
    common latency-related stats.

    Args:
        filepath (str): The path to the stats.txt file.

    Returns:
        Dict[str, Union[float, str]]: A dictionary containing the parsed statistics.
                                      Values are floats or strings for 'nan'/'inf'.
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

    mem_ctrl_latency_suffixes = {}
    # mem_ctrl_latency_suffixes = {
    #     ".priorityMinLatency",
    #     ".priorityMaxLatency",
    #     ".dram.avgQLat",
    #     ".dram.avgBusLat",
    #     ".dram.avgMemAccLat",
    # }
    
    mem_ctrl_prefix_regex = re.compile(r'system\.mem_ctrls\d+')

    with open(filepath, 'r') as f:
        for line in f:
            # **THE FIX:** Normalize all varied whitespace into single spaces.
            # This handles tabs, non-breaking spaces, and multiple spaces.
            normalized_line = re.sub(r'\s+', ' ', line).strip()
            
            match = STAT_REGEX.match(normalized_line)
            if not match:
                continue

            key = match.group(1)
            
            is_target_stat = (
                key in exact_latency_keys or
                (mem_ctrl_prefix_regex.match(key) and any(key.endswith(s) for s in mem_ctrl_latency_suffixes))
            )

            if is_target_stat:
                value_str = match.group(2)
                try:
                    stats[key] = float(value_str)
                except ValueError:
                    stats[key] = value_str
                    
    return stats

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

def save_experiment_run_data(config, stats, output_dir="experiment_runs"):
    """Saves data for an experiment run with a high-precision timestamp."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # High-precision timestamp including microseconds
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    run_name = f"exp_run_{timestamp}"
    run_data = {"run_name": run_name, "timestamp": timestamp, "config": config, "stats": stats}
    file_path = os.path.join(output_dir, f"{run_name}.json")
    with open(file_path, 'w') as f:
        json.dump(run_data, f, indent=4)
    return file_path