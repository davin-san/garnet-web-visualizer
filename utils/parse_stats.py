import json
import re
import os
import math
from typing import Dict, Any
from datetime import datetime

STAT_REGEX = re.compile(
    # Updated regex to correctly capture 'nan', 'inf', '-inf'
    r"([a-zA-Z0-9_:\.\-]+) ([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|nan|-?inf)"
)


def parse_stats_file(filepath: str = "m5out/stats.txt") -> Dict[str, float]:
    """
    Parses a gem5 stats.txt file, extracting and aggregating a curated list
    of important, common system-focused stats.

    Args:
        filepath (str): The path to the stats.txt file.

    Returns:
        Dict[str, float]: A dictionary containing the parsed statistics.
                          All values are floats. 'nan'/'inf' are preserved
                          as their float representations.
    """
    # Explicitly type the stats dictionary
    stats: Dict[str, float] = {}
    if not os.path.exists(filepath):
        print(f"Warning: Stats file not found at {filepath}")
        return stats

    exact_keys = {
        # Simulation time stats
        "simSeconds", "simTicks", "finalTick",
        # Host machine stats
        "hostSeconds", "hostTickRate", "hostMemory",
        # Workload stats
        "system.workload.inst.arm",
        # Ruby network-on-chip (NoC) overall stats
        "system.ruby.network.average_flit_latency",
        "system.ruby.network.average_packet_latency",
        "system.ruby.network.average_hops",
        "system.ruby.network.avg_link_utilization",
    }

    # mem_ctrl_prefix_regex = re.compile(r'system\.mem_ctrls\d+')

    # Add variables for aggregation.
    total_l1_demand_hits = 0
    total_l1_demand_misses = 0
    total_dram_energy_pj = 0.0

    with open(filepath, 'r') as f:
        for line in f:
            normalized_line = re.sub(r'\s+', ' ', line).strip()
            match = STAT_REGEX.match(normalized_line)
            if not match:
                continue

            key = match.group(1)
            value_str = match.group(2)

            try:
                # This is the correct way to parse.
                # float() correctly handles "nan", "inf", and "-inf".
                value = float(value_str)
            except ValueError:
                # This should only happen if the regex is wrong
                print(f"Warning: Could not parse value '{value_str}' for key '{key}'. Skipping.")
                continue

            # --- Key-based parsing and aggregation ---

            # 1. Parse exact keys
            if key in exact_keys:
                stats[key] = value

            # 2. Parse per-memory controller stats
            # elif mem_ctrl_prefix_regex.match(key) and any(key.endswith(s) for s in mem_ctrl_latency_suffixes):
            #     stats[key] = value

            # 3. Aggregate L1 cache stats
            elif key.endswith(".cacheMemory.m_demand_hits"):
                if "l1_cntrl" in key:
                    # Hits/misses must be finite integers.
                    # Check before casting to avoid 'int(float("nan"))'.
                    if math.isfinite(value):
                        total_l1_demand_hits += int(value)
            elif key.endswith(".cacheMemory.m_demand_misses"):
                if "l1_cntrl" in key:
                    if math.isfinite(value):
                        total_l1_demand_misses += int(value)

            # 4. Aggregate total DRAM energy
            #    This is safe because 'value' is guaranteed to be a float.
            elif key.endswith(".dram.rank.totalEnergy"):  # Gem5 23+
                total_dram_energy_pj += value
            elif ".dram.rank" in key and key.endswith(".totalEnergy"):  # Older Gem5
                total_dram_energy_pj += value

    # Calculate and add aggregated stats to the final dictionary.
    total_l1_accesses = total_l1_demand_hits + total_l1_demand_misses
    if total_l1_accesses > 0:
        stats["system.ruby.l1_overall_hit_rate"] = total_l1_demand_hits / total_l1_accesses
    else:
        # Use 0.0 as a safe, JSON-serializable default instead of "nan"
        stats["system.ruby.l1_overall_hit_rate"] = 0.0

    stats["system.dram.total_energy_pj"] = total_dram_energy_pj
    stats["system.dram.total_energy_nj"] = total_dram_energy_pj / 1000.0  # Convert to nanojoules

    return stats

# Add type hints for config and stats
def save_run_data(config: Any, stats: Dict[str, float], output_dir: str = "run_data"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_name = f"run_{timestamp}"
    
    # config can be any JSON-serializable structure
    run_data: Dict[str, Any] = {
        "run_name": run_name,
        "timestamp": timestamp,
        "config": config,
        "stats": stats
    }
    
    file_path = os.path.join(output_dir, f"{run_name}.json")
    with open(file_path, 'w') as f:
        # Since stats is Dict[str, float] (with 0.0 for nan hit rate),
        # this is now safe for JSON, though 'inf' values will become "Infinity"
        json.dump(run_data, f, indent=4)
    print(f"Successfully saved run data to {file_path}")
    return run_name

# Add type hints for config and stats
def save_experiment_run_data(config: Any, stats: Dict[str, float], output_dir: str = "experiment_runs"):
    """Saves data for an experiment run with a high-precision timestamp."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # High-precision timestamp including microseconds
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    run_name = f"exp_run_{timestamp}"
    
    run_data: Dict[str, Any] = {
        "run_name": run_name,
        "timestamp": timestamp,
        "config": config,
        "stats": stats
    }
    
    file_path = os.path.join(output_dir, f"{run_name}.json")
    with open(file_path, 'w') as f:
        json.dump(run_data, f, indent=4)
    return file_path