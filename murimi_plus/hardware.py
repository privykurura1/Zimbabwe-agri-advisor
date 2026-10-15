"""Low-end hardware mode: pick llama-server settings that fit the computer.

Honest numbers for the shipped model (Qwen2.5-1.5B Q4_K_M, ~1 GB file): most of
the memory is the model itself. Cutting the context from 4096 to 2048 tokens
saves only around 60 MB (my estimate from the model's published layer sizes;
check with Task Manager). Measured with this app's own prompts, the longest
prompt is about 1,200 tokens, plus up to 350 answer tokens, so 2048 still fits.

What really helps a weak laptop:
  * fewer threads than logical cores (hyper-threads slow llama.cpp down),
  * a smaller model file - ONLY if it passes test_model_behaviour.py first.
    Put it at model/lite.gguf; it is used when the computer has under 4 GB RAM,
    or always when MURIMIFARA_LOW_END=1.
"""
import ctypes
import os
import sys

MAIN_MODEL = os.path.join("model", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
LITE_MODEL = os.path.join("model", "lite.gguf")


def total_ram_gb():
    """Physical memory in GB, or None if it cannot be read."""
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys / 1024 ** 3
            return None
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024 ** 2
    except (OSError, ValueError, AttributeError):
        return None
    return None


def choose(base_dir, ram_gb=None, cpus=None, force_low=None):
    """Arguments for llama-server and a short description of why."""
    ram_gb = total_ram_gb() if ram_gb is None else ram_gb
    cpus = cpus or os.cpu_count() or 2
    if force_low is None:
        force_low = os.environ.get("MURIMIFARA_LOW_END") == "1"
    low = force_low or (ram_gb is not None and ram_gb < 6)
    threads = max(1, min(4, cpus // 2 if cpus >= 4 else cpus))
    model = MAIN_MODEL
    lite = os.path.join(base_dir, LITE_MODEL)
    if os.path.exists(lite) and (force_low or (ram_gb is not None and ram_gb < 4)):
        model = LITE_MODEL
    args = ["-m", os.path.join(base_dir, model), "-t", str(threads), "-c", "2048" if low else "4096"]
    ram = f"{ram_gb:.1f} GB RAM" if ram_gb is not None else "RAM unknown"
    why = f"{'low-end' if low else 'normal'} mode: {ram}, {cpus} logical CPUs -> {threads} threads, model {model}"
    return args, why
