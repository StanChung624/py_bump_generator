from typing import Callable, List
from VBump.Basic import VBump, load_csv, to_csv, _emit_log

def merge(source_dirs:List[str], target_dir: str, log_callback: Callable[[str], None] | None = None):
    vbumps = []
    for src_file in source_dirs:
        _emit_log(log_callback, f"Loading from '{src_file}'...")
        vbumps += load_csv(src_file, log_callback=log_callback)

    to_csv(target_dir, vbumps, log_callback=log_callback)

