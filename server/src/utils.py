import secrets
import string
import psutil
import platform
from pathlib import Path


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
    """Get current memory usage"""
    mem = psutil.virtual_memory()
    return {
        "total_mb": int(mem.total / (1024 * 1024)),
        "used_mb": int(mem.used / (1024 * 1024)),
        "available_mb": int(mem.available / (1024 * 1024)),
        "percent": mem.percent,
    }


def get_cpu_usage() -> float:
    """Get current CPU usage percentage"""
    return psutil.cpu_percent(interval=1)
