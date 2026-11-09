"""Measure a real bounded export. Reports never include the private source path."""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import threading
import time
from pathlib import Path

from framepick import encoding
from framepick.media import Tools, probe
from framepick.model import Clip, ExportSettings

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("--start", type=float, default=0)
parser.add_argument("--duration", type=float, default=5)
parser.add_argument("--output", type=Path, default=Path("artifacts/benchmark"))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
tools = Tools.discover()
info = probe(args.source, tools)
peaks = []
original_popen = encoding.subprocess.Popen


class MemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def measured_popen(*popen_args, **kwargs):
    process = original_popen(*popen_args, **kwargs)
    original_poll = process.poll
    samples = {"peak_working_set_bytes": 0}
    peaks.append(samples)

    def poll():
        if sys.platform == "win32":
            counters = MemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.c_void_p(int(process._handle)), ctypes.byref(counters), counters.cb
            ):
                samples["peak_working_set_bytes"] = max(
                    samples["peak_working_set_bytes"], counters.PeakWorkingSetSize
                )
        return original_poll()

    process.poll = poll
    return process


encoding.subprocess.Popen = measured_popen
started = time.monotonic()
log_path = args.output / "benchmark.log"
try:
    with log_path.open("w", encoding="utf-8") as log:
        output = encoding.export_gif(
            tools,
            args.source,
            Clip(round(args.start * 1000), round(args.duration * 1000)),
            ExportSettings(480, 15),
            args.output,
            threading.Event(),
            lambda stage, value: print(f"{stage}: {value:.0%}", flush=True),
            lambda text: log.write(text + "\n"),
        )
finally:
    encoding.subprocess.Popen = original_popen
elapsed = time.monotonic() - started
result_info = probe(output, tools)
report = {
    "source_duration_ms": info.duration_ms,
    "source_dimensions": [info.width, info.height],
    "source_fps": info.fps,
    "requested_start_ms": round(args.start * 1000),
    "requested_duration_ms": round(args.duration * 1000),
    "output_duration_ms": result_info.duration_ms,
    "output_dimensions": [result_info.width, result_info.height],
    "output_bytes": output.stat().st_size,
    "elapsed_seconds": round(elapsed, 3),
    "child_processes": peaks,
}
(args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
