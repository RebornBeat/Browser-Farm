import secrets
import string
import psutil
import platform
import threading
import time
from pathlib import Path

# ---------------------------------------------------------
# BACKGROUND SYSTEM MONITOR (Non-Blocking)
# ---------------------------------------------------------

# Global cache for system stats
_cached_stats = {
    "cpu_percent": 0.0,
    "memory": {
        "total_mb": 0,
        "used_mb": 0,
        "available_mb": 0,
        "percent": 0.0,
    }
}

def _monitor_loop():
    """
    Background thread that updates system stats every 2 seconds.
    This ensures that API calls to /health are non-blocking.
    """
    # Give a small initial delay to allow app to boot
    time.sleep(1)

    while True:
        try:
            # 1. Get CPU (This blocks for 1 second, but in a separate thread so it's fine)
            cpu = psutil.cpu_percent(interval=1)

            # 2. Get Memory
            mem = psutil.virtual_memory()

            # 3. Update Cache
            _cached_stats["cpu_percent"] = cpu
            _cached_stats["memory"] = {
                "total_mb": int(mem.total / (1024 * 1024)),
                "used_mb": int(mem.used / (1024 * 1024)),
                "available_mb": int(mem.available / (1024 * 1024)),
                "percent": mem.percent,
            }

        except Exception as e:
            # Log error or just ignore to keep thread alive
            print(f"Error in monitor loop: {e}")
            time.sleep(2)

# Start the background thread immediately on import
_monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
_monitor_thread.start()


# ---------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------

def generate_api_key() -> str:
    """Generate a random API key"""
    alphabet = string.ascii_letters + string.digits
    return "bf_" + "".join(secrets.choice(alphabet) for _ in range(32))


def get_system_info() -> dict:
    """Get system information"""
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
    }


def get_memory_usage() -> dict:
    """
    Get current memory usage (Non-blocking).
    Returns cached data updated by background thread.
    """
    return _cached_stats["memory"]


def get_cpu_usage() -> float:
    """
    Get current CPU usage percentage (Non-blocking).
    Returns cached data updated by background thread.
    """
    return _cached_stats["cpu_percent"]
