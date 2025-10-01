from typing import List
from VBump.Basic import VBump, load_csv, to_csv

def merge(source_dirs:List[str], target_dir):
    vbumps = []
    for src_file in source_dirs:
        print(f"💿 load from {src_file}...", end='')
        vbumps += load_csv(src_file) 
        print('done.')

    to_csv(target_dir, vbumps)

