from typing import Callable, List, Dict

from VBump.Basic import VBump, _require_h5py, _require_numpy, _emit_log

def make_move_func(dx, dy, dz, *,
                   new_group:int|None=None,
                   new_D:float|None=None,
                   group_map:Dict[int,int]|None = None,
                   keep_original:bool=False):
    
    def move_and_duplicate(row):
        original = row.copy()
        moved = row.copy()
        moved['x0'] += dx
        moved['x1'] += dx
        moved['y0'] += dy
        moved['y1'] += dy
        moved['z0'] += dz
        moved['z1'] += dz        
        if new_D is not None:
            moved['diameter'] = new_D

        if group_map and moved['group'] in group_map:
            moved['group'] = group_map[moved['group']]
        elif new_group is not None:
            moved['group'] = new_group
        
        if keep_original:
            return [original, moved]
        else:
            return [moved]
    return move_and_duplicate

def modify_vbump_hdf5(
    src_path: str,
    dst_path: str,
    *,
    modify_func: Callable[[dict], List[dict]],
    chunk_size: int = 1_000_000,
    dataset_name: str = "vbump",
    output_name: str | None = None,
    log_callback: Callable[[str], None] | None = None
) -> None:
    """
    Copy vbump dataset, apply modify_func to each row,
    and update each group's bounding_box accordingly.
    """

    h5py = _require_h5py()
    np = _require_numpy()

    with h5py.File(src_path, 'r') as fin, h5py.File(dst_path, 'w') as fout:
        # === Step 1. 檢查原始 dataset ===
        if dataset_name not in fin:
            raise KeyError(f"Dataset '{dataset_name}' not found.")
        dset_in = fin[dataset_name]
        dtype = dset_in.dtype
        total = dset_in.shape[0]
        _emit_log(log_callback, f"Source dataset loaded: {total:,} rows.")

        target_dataset_name = output_name or dataset_name

        # === Step 2. 建立輸出 dataset ===
        dset_out = fout.create_dataset(
                            target_dataset_name,
                            shape=(0,),
                            maxshape=(None,),
                            dtype=dtype,
                            chunks=True
                        )
        _emit_log(log_callback, f"Target dataset '{target_dataset_name}' created successfully.")

        # === Step 3. 複製 groups 架構（但稍後會更新 bbox） ===
        if 'groups' in fin:
            fin.copy('groups', fout)
            fout_groups = fout['groups']
        else:
            fout_groups = fout.create_group('groups')

        # === Step 4. 建立 group bbox 暫存器 ===
        group_bbox = {}  # {gid: [xmin, ymin, zmin, xmax, ymax, zmax]}
        overall_bbox: list[float] | None = None

        # === Step 5. 分 chunk 處理 ===
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            arr = dset_in[start:end]
            new_rows = []

            for row in arr:
                r = {name: row[name].item() for name in row.dtype.names}
                result_list = modify_func(r)

                for new_r in result_list:
                    new_row = tuple(new_r[name] for name in row.dtype.names)
                    new_rows.append(new_row)

                    # 更新 bounding box
                    gid = int(new_r['group'])
                    x_list = [float(new_r['x0']), float(new_r['x1'])]
                    y_list = [float(new_r['y0']), float(new_r['y1'])]
                    z_list = [float(new_r['z0']), float(new_r['z1'])]

                    x_min, x_max = min(x_list), max(x_list)
                    y_min, y_max = min(y_list), max(y_list)
                    z_min, z_max = min(z_list), max(z_list)

                    if gid not in group_bbox:
                        group_bbox[gid] = [x_min, y_min, z_min, x_max, y_max, z_max]
                    else:
                        bbox = group_bbox[gid]
                        bbox[0] = min(bbox[0], x_min)
                        bbox[1] = min(bbox[1], y_min)
                        bbox[2] = min(bbox[2], z_min)
                        bbox[3] = max(bbox[3], x_max)
                        bbox[4] = max(bbox[4], y_max)
                        bbox[5] = max(bbox[5], z_max)

                    if overall_bbox is None:
                        overall_bbox = [x_min, y_min, z_min, x_max, y_max, z_max]
                    else:
                        overall_bbox[0] = min(overall_bbox[0], x_min)
                        overall_bbox[1] = min(overall_bbox[1], y_min)
                        overall_bbox[2] = min(overall_bbox[2], z_min)
                        overall_bbox[3] = max(overall_bbox[3], x_max)
                        overall_bbox[4] = max(overall_bbox[4], y_max)
                        overall_bbox[5] = max(overall_bbox[5], z_max)

            # 寫入新 chunk
            arr_out = np.array(new_rows, dtype=dtype)
            if start == 0:
                dset_out.resize((len(arr_out),))
                dset_out[:] = arr_out
            else:
                old_size = dset_out.shape[0]
                new_size = old_size + len(arr_out)
                dset_out.resize((new_size,))
                dset_out[old_size:new_size] = arr_out

            _emit_log(log_callback, f"Processed chunk {start:,}-{end:,}: {len(arr_out):,} rows.")

            del arr
            del arr_out

        # === Step 6. 寫回更新後的 bounding_box ===
        for gid, bbox in group_bbox.items():
            if str(gid) not in fout_groups:
                subgroup = fout_groups.create_group(str(gid))
            else:
                subgroup = fout_groups[str(gid)]
            subgroup.attrs['bounding_box'] = (
                (bbox[0], bbox[1], bbox[2]),
                (bbox[3], bbox[4], bbox[5])
            )

        if overall_bbox is not None:
            dset_out.attrs['bounding_box'] = (
                (overall_bbox[0], overall_bbox[1], overall_bbox[2]),
                (overall_bbox[3], overall_bbox[4], overall_bbox[5]),
            )

        _emit_log(log_callback, f"Updated bounding boxes for {len(group_bbox)} groups.")

def merge_hdf5(
    src_paths: List[str],
    dst_path: str,
    *,
    dataset_name: str = "vbump",
    output_name: str | None = None,
    chunk_size: int = 1_000_000,
    log_callback: Callable[[str], None] | None = None
) -> None:
    """
    Merge multiple vbump HDF5 datasets into one file.
    Preserve 'groups' structure and recompute bounding boxes.
    """
    h5py = _require_h5py()
    np = _require_numpy()

    # === Step 1. 建立輸出檔案 ===
    with h5py.File(dst_path, 'w') as fout:
        target_dataset_name = output_name or dataset_name
        dset_out = None
        group_bbox: dict[int, list[float]] = {}
        overall_bbox: list[float] | None = None

        for path in src_paths:
            with h5py.File(path, 'r') as fin:
                if dataset_name not in fin:
                    _emit_log(log_callback, f"Warning: Skipping '{path}', dataset '{dataset_name}' not found.")
                    continue

                dset_in = fin[dataset_name]
                dtype = dset_in.dtype
                total = dset_in.shape[0]
                _emit_log(log_callback, f"Merging file '{path}' ({total:,} rows)...")

                # 若第一個檔案，建立輸出 dataset
                if dset_out is None:
                    dset_out = fout.create_dataset(
                        target_dataset_name,
                        shape=(0,),
                        maxshape=(None,),
                        dtype=dtype,
                        chunks=True
                    )

                # === Step 2. 分 chunk 讀取與寫入 ===
                for start in range(0, total, chunk_size):
                    end = min(start + chunk_size, total)
                    arr = dset_in[start:end]

                    # 更新 group bbox
                    for row in arr:
                        gid = int(row['group'])
                        x_list = [float(row['x0']), float(row['x1'])]
                        y_list = [float(row['y0']), float(row['y1'])]
                        z_list = [float(row['z0']), float(row['z1'])]
                        x_min, x_max = min(x_list), max(x_list)
                        y_min, y_max = min(y_list), max(y_list)
                        z_min, z_max = min(z_list), max(z_list)

                        if gid not in group_bbox:
                            group_bbox[gid] = [x_min, y_min, z_min, x_max, y_max, z_max]
                        else:
                            bbox = group_bbox[gid]
                            bbox[0] = min(bbox[0], x_min)
                            bbox[1] = min(bbox[1], y_min)
                            bbox[2] = min(bbox[2], z_min)
                            bbox[3] = max(bbox[3], x_max)
                            bbox[4] = max(bbox[4], y_max)
                            bbox[5] = max(bbox[5], z_max)

                        if overall_bbox is None:
                            overall_bbox = [x_min, y_min, z_min, x_max, y_max, z_max]
                        else:
                            overall_bbox[0] = min(overall_bbox[0], x_min)
                            overall_bbox[1] = min(overall_bbox[1], y_min)
                            overall_bbox[2] = min(overall_bbox[2], z_min)
                            overall_bbox[3] = max(overall_bbox[3], x_max)
                            overall_bbox[4] = max(overall_bbox[4], y_max)
                            overall_bbox[5] = max(overall_bbox[5], z_max)

                    # 寫入新 chunk
                    old_size = dset_out.shape[0]
                    new_size = old_size + len(arr)
                    dset_out.resize((new_size,))
                    dset_out[old_size:new_size] = arr

                    _emit_log(log_callback, f"Processed chunk {start:,}-{end:,} for '{path}'.")

                # === Step 3. 合併 groups ===
                if 'groups' in fin:
                    if 'groups' not in fout:
                        fout_groups = fout.create_group('groups')
                    else:
                        fout_groups = fout['groups']

                    for gid, subgroup in fin['groups'].items():
                        if gid not in fout_groups:
                            fin.copy(f'groups/{gid}', fout_groups)

        # === Step 4. 更新 bounding box ===
        if dset_out is not None:
            fout_groups = fout.get('groups', fout.create_group('groups'))
            for gid, bbox in group_bbox.items():
                if str(gid) not in fout_groups:
                    subgroup = fout_groups.create_group(str(gid))
                else:
                    subgroup = fout_groups[str(gid)]
                subgroup.attrs['bounding_box'] = (
                    (bbox[0], bbox[1], bbox[2]),
                    (bbox[3], bbox[4], bbox[5])
                )

            if overall_bbox is not None:
                dset_out.attrs['bounding_box'] = (
                    (overall_bbox[0], overall_bbox[1], overall_bbox[2]),
                    (overall_bbox[3], overall_bbox[4], overall_bbox[5])
                )

            _emit_log(log_callback, f"Successfully merged {len(src_paths)} files and updated {len(group_bbox)} group bounding boxes.")
        else:
            _emit_log(log_callback, "Warning: No valid datasets were merged.")