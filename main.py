from __future__ import annotations

from typing import List, Tuple

from VBumpDef import VBump, load_csv, to_csv, load_hdf5, to_hdf5
from createRectangularArea import (
    LARGE_VBUMP_THRESHOLD,
    bounding_box_vbumps_for_rectangular_area,
    create_rectangular_area_XY_by_number,
    create_rectangular_area_XY_by_number_to_hdf5,
    create_rectangular_area_XY_by_pitch,
    create_rectangular_area_XY_by_pitch_to_hdf5,
    estimate_rectangular_area_XY_by_number_count,
    estimate_rectangular_area_XY_by_pitch_count,
    normalize_rectangular_area_from_counts,
)
from fileManipulation import merge
from vbumps2WDL import (
    vbump_2_wdl_as_airtrap,
    vbump_2_wdl_as_weldline,
    vbump_2_wdl_as_weldline_AABB,
    plot_vbumps,
    plot_vbumps_aabb
)
from vbumpsManipulation import modify_diameter, modify_height, move_vbumps

GREEN = "\033[92m"
RESET = "\033[0m"


def gprint(message: str) -> None:
    print(f"{GREEN}{message}{RESET}")


def prompt_float(label: str, defualt:float=None) -> float|None:
    """Ask the user for a float value and keep trying until we get one."""
    while True:
        raw = input(f"{label}: ").strip()
        if not raw:
            return defualt
        try:
            return float(raw)
        except ValueError:
            gprint("Please enter a numeric value.")


def prompt_int(label: str, default:int=None) -> int|None:
    while True:
        raw = input(f"{label}: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            gprint("Please enter an integer value.")


def prompt_point(label: str, dimensions: int) -> Tuple[float, ...]:
    coords: List[float] = []
    for axis in range(dimensions):
        coords.append(prompt_float(f"{label} - axis {axis}"))
    return tuple(coords)


def prompt_yes_no(label: str, default: bool = False) -> bool:
    default_msg = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{label} {default_msg}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        gprint("Please answer with y or n.")

def display_welcome_banner()->None:
    dino = """
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣶⣶⣶⣶⣶⢾⣿⣿⣿⣿⣿⣻⣶⡦⣤⣤⣤⣤⣤⣤⣤⣤⣄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣿⣿⣿⣿⣄⣘⣻⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⠞⠱⣿⣿⣿⡟⠉⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⡿⠿⠘⢽⣿⡿⣿⣿⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⡿⣿⠹⠉⡺⣿⣿⣿⣶⣤⣿⣿⣿⣿⣯⣽⣿⣿⢣⡸⣿⡏⠙⠒⠛⠉⢛⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢀⣰⣿⡇⠃⠁⡀⣠⠀⣟⣿⣿⣾⣿⣿⣿⣿⣿⣿⣻⣿⣯⣇⣺⣩⣇⠠⣄⠀⠀⣶⡽⣿⣩⣧⣷⣾⣿⣿⣿⣿⠇⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⢗⠯⠀⡄⡔⡿⣿⣏⠳⠈⠻⣻⠟⠻⠛⢋⣁⠋⠻⢽⠿⡿⢿⣿⣿⠿⣟⣭⣽⣶⣿⣿⣿⣿⣿⣿⡿⠛⠁⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣼⣽⣻⠀⡀⡸⢃⣾⠁⠛⠟⠂⣁⣠⣴⣶⣿⣿⣿⣿⣿⣿⣿⣾⣶⣷⣾⣾⣿⣿⣿⣿⣿⣿⣿⡿⠿⠿⠛⠋⠁⠀⠀⠀⠀⠀⠀
       ⣰⣿⣻⣻⢀⣴⣇⣃⠷⣤⣠⣶⣿⣿⢿⠿⣿⣿⢿⢛⣛⣯⣿⣿⡿⠿⣿⣿⣿⠿⣟⣿⣿⣽⣿⣾⣿⣿⣿⣿⣷          virtual bump csv generator
⠀⠀⠀⠀⠀⣴⣿⣿⠟⢿⣋⢝⠏⣶⣤⣼⣿⣿⣆⣀⣸⣶⣷⣿⣿⣟⣿⣽⣿⣿⣿⣷⣶⣶⡤⣌⣶⣔⣯⣿⣿⣿⣿⣿⣿⣿⡿⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢰⣿⣿⡿⣅⠀⠹⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⣿⠟⢽⣟⣿⣿⣿⣿⣿⣿⣿⡿⠿⠿⠛⠋⠁⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢸⣿⢿⣷⣌⣛⢿⣿⣿⣿⣿⣿⣿⣛⢋⣿⣯⣿⡭⢻⣿⣿⣿⣿⣗⣻⣬⣷⣤⣿⣿⣿⡿⠟⣛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣿⣿⣿⣿⣍⠓⣾⣿⣿⣿⣿⣿⣿⣿⣿⣽⣿⣿⣿⣿⣿⣿⣯⣿⣿⣿⣿⣿⠿⢛⣭⡷⠿⠿⣿⣿⣿⣷⣶⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀                v1
⠀⠀⠀⢸⣿⣿⢯⡻⣝⠿⠦⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠛⠉⠁⠀⠀⠀⠀⠀⠀⠀⠉⠙⢿⣿⣿⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⢸⣿⣿⠷⡈⠈⢳⡉⠛⠿⢻⣿⣾⣻⣿⣿⣿⣿⣿⠿⠛⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀   
⠀⠀⠀⣸⡿⢿⡟⠲⣼⠦⠵⣤⣌⣜⣿⣼⣿⣿⣿⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀
⠀⠀⠀⣿⡙⢮⠳⡀⠈⣣⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣧⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⡇⠀⢸⣿⠁⠀⠀⠉⠉⢿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠁⠀⠘⢿⠀⠀⠀⠀⠀⠈⠻⢿⠿⠿⠿⠟⠛⠃"""
    gprint(dino)

def display_menu() -> None:
    gprint("\n=== Virtual Bump Console ===")
    gprint("1) Load VBump CSV")
    gprint("2) Save VBump CSV")
    gprint("3) Create rectangular area (pitch)")
    gprint("4) Create rectangular area (count)")
    gprint("5) Modify diameter")
    gprint("6) Move/Copy vbumps")
    gprint("7) Export to WDL (weldline)")
    gprint("8) Export to WDL (airtrap)")
    gprint("9) Merge CSV files")
    gprint("10) Plot vbumps AABB (with substrate box)")  
    gprint("11) Set substrate box corners")             
    gprint("0) Exit")


def main() -> None:
    current_vbumps: List[VBump] = []
    substrate_p0: Tuple[float, float, float] | None = None
    substrate_p1: Tuple[float, float, float] | None = None
    display_welcome_banner()
    while True:
        gprint(f"\nCurrent bump count: {len(current_vbumps)}")
        display_menu()
        choice = input("Select an option: ").strip()

        if choice == "1":
            path = input("Path to CSV/HDF5 file: ").strip()
            try:
                if path.lower().endswith(('.h5', '.hdf5')):
                    new_vbumps = load_hdf5(path, max_rows=LARGE_VBUMP_THRESHOLD)
                    gprint("Loaded HDF5 dataset.")
                    if getattr(new_vbumps, "is_bounding_box_only", False):
                        gprint(
                            f"⚠️ Source contains {new_vbumps.source_count:,} bumps. Loaded bounding-box markers instead (threshold {LARGE_VBUMP_THRESHOLD:,})."
                        )
                else:
                    new_vbumps = load_csv(path)
                # Ask if user wants to change group ID
                if prompt_yes_no("Change group ID of loaded bumps?", False):
                    new_group = prompt_int("Enter new group ID", None)
                    if new_group is not None:
                        for b in new_vbumps:
                            b.group = new_group
                        gprint(f"All loaded bumps set to group {new_group}.")
                if prompt_yes_no("Replace current list with the new bumps? (No: append to current)", True):
                    current_vbumps = list(new_vbumps)
                else:
                    current_vbumps.extend(new_vbumps)
            except FileNotFoundError:
                gprint("CSV/HDF5 file not found.")
            except Exception as exc:
                gprint(f"Failed to load file: {exc}")

        elif choice == "2":
            if not current_vbumps:
                gprint("Nothing to save yet.")
                continue
            path = input("Target CSV path: ").strip()
            to_csv(path, current_vbumps)

        elif choice == "3":
            p0 = prompt_point("Lower corner (x, y)", 2)
            p1 = prompt_point("Upper corner (x, y)", 2)
            x_pitch = prompt_float("X pitch")
            y_pitch = prompt_float("Y pitch")
            diameter = prompt_float("Diameter")
            group = prompt_int("Group", 1)
            z = prompt_float("Base Z")
            height = prompt_float("Height")
            estimated = estimate_rectangular_area_XY_by_pitch_count(p0, p1, x_pitch, y_pitch)
            if estimated >= LARGE_VBUMP_THRESHOLD:
                gprint(
                    f"⚠️ The requested grid would generate {estimated:,} vbumps, which exceeds the in-memory limit ({LARGE_VBUMP_THRESHOLD:,})."
                )
                gprint(
                    "The full dataset will be streamed to an HDF5 file and only two bounding-box markers will remain in memory."
                )
                hdf5_path = ""
                while not hdf5_path:
                    hdf5_path = input("HDF5 output path: ").strip()
                    if not hdf5_path:
                        gprint("Please provide a valid file path.")
                create_rectangular_area_XY_by_pitch_to_hdf5(
                    hdf5_path,
                    p0,
                    p1,
                    x_pitch,
                    y_pitch,
                    diameter,
                    group,
                    z,
                    height,
                    log_callback=lambda msg: gprint(msg),
                )
                new_vbumps = bounding_box_vbumps_for_rectangular_area(
                    p0, p1, z, height, diameter, group
                )
                gprint(
                    f"📏 Stored {len(new_vbumps)} bounding-box markers in memory. Full dataset saved to {hdf5_path}."
                )
            else:
                new_vbumps = create_rectangular_area_XY_by_pitch(
                    p0, p1, x_pitch, y_pitch, diameter, group, z, height
                )
            if prompt_yes_no("Replace current list with the new bumps? (No: append to current)", True):
                current_vbumps = new_vbumps
            else:
                current_vbumps.extend(new_vbumps)

        elif choice == "4":
            p0 = prompt_point("Lower corner (x, y)", 2)
            p1 = prompt_point("Upper corner (x, y)", 2)
            x_num = prompt_int("Number of bumps along X", 10)
            y_num = prompt_int("Number of bumps along Y", 10)
            diameter = prompt_float("Diameter")
            group = prompt_int("Group", 1)
            z = prompt_float("Base Z")
            height = prompt_float("Height")
            estimated = estimate_rectangular_area_XY_by_number_count(x_num, y_num)
            if estimated >= LARGE_VBUMP_THRESHOLD:
                gprint(
                    f"⚠️ The requested grid would generate {estimated:,} vbumps, which exceeds the in-memory limit ({LARGE_VBUMP_THRESHOLD:,})."
                )
                gprint(
                    "The full dataset will be streamed to an HDF5 file and only two bounding-box markers will remain in memory."
                )
                hdf5_path = ""
                while not hdf5_path:
                    hdf5_path = input("HDF5 output path: ").strip()
                    if not hdf5_path:
                        gprint("Please provide a valid file path.")
                new_p0, new_p1, x_pitch, y_pitch = normalize_rectangular_area_from_counts(p0, p1, x_num, y_num)
                create_rectangular_area_XY_by_number_to_hdf5(
                    hdf5_path,
                    p0,
                    p1,
                    x_num,
                    y_num,
                    diameter,
                    group,
                    z,
                    height,
                    log_callback=lambda msg: gprint(msg),
                )
                new_vbumps = bounding_box_vbumps_for_rectangular_area(
                    new_p0, new_p1, z, height, diameter, group
                )
                gprint(
                    f"📏 Stored {len(new_vbumps)} bounding-box markers in memory. Full dataset saved to {hdf5_path}."
                )
            else:
                new_vbumps = create_rectangular_area_XY_by_number(
                    p0, p1, x_num, y_num, diameter, group, z, height
                )
            if prompt_yes_no("Replace current list with the new bumps? (No: append to current)", True):
                current_vbumps = new_vbumps
            else:
                current_vbumps.extend(new_vbumps)

        elif choice == "5":
            if not current_vbumps:
                gprint("Load or create bumps first.")
                continue

            # Ask if user wants to filter by group
            filter_by_group = prompt_yes_no("Select bumps by group ID?", False)
            if filter_by_group:
                group_id = prompt_int("Enter group ID to select", None)
                selected_bumps = [b for b in current_vbumps if b.group == group_id]
                if not selected_bumps:
                    gprint(f"No bumps found with group ID {group_id}.")
                    continue
            else:
                selected_bumps = current_vbumps

            new_diameter = prompt_float("New diameter")
            modify_diameter(selected_bumps, new_diameter)
            gprint("Diameters updated.")

        elif choice == "6":
            if not current_vbumps:
                gprint("Load or create bumps first.")
                continue

            # Ask if user wants to filter by group
            filter_by_group = prompt_yes_no("Select bumps by group ID?", False)
            if filter_by_group:
                group_id = prompt_int("Enter group ID to select", None)
                selected_bumps = [b for b in current_vbumps if b.group == group_id]
                if not selected_bumps:
                    gprint(f"No bumps found with group ID {group_id}.")
                    continue
            else:
                selected_bumps = current_vbumps

            reference = prompt_point("Reference point (x, y, z)", 3)
            new_point = prompt_point("Target point (x, y, z)", 3)
            keep_origin = prompt_yes_no("Keep the original bumps as well?", False)
            if keep_origin:
                new_diameter = prompt_float("Assign new diameter", None)
                new_group = prompt_int("Assign new group ID", None)
            else:
                new_diameter = None
                new_group = None

            # Only move/copy the selected bumps
            result_bumps = move_vbumps(selected_bumps, reference, new_point, new_group, new_diameter, keep_origin)

            if filter_by_group and not keep_origin:
                # Replace only the selected group in current_vbumps
                current_vbumps = [b for b in current_vbumps if not (b.group == group_id)] + result_bumps
            elif filter_by_group and keep_origin:
                # Add the new bumps to the full list
                current_vbumps.extend(result_bumps)
            else:
                # No filter: replace or extend the whole list as before
                current_vbumps = result_bumps

        elif choice == "7":
            if not current_vbumps:
                gprint("Load or create bumps first.")
                continue
            path = input("WDL output path (weldline): ").strip()
            if (len(current_vbumps) < 300000):
                vbump_2_wdl_as_weldline(path, current_vbumps)
            else:
                gprint("vbump number > 300,000, output boxes instead.")
                vbump_2_wdl_as_weldline_AABB(path, current_vbumps)

        elif choice == "8":
            if not current_vbumps:
                gprint("Load or create bumps first.")
                continue
            path = input("WDL output path (airtrap): ").strip()
            vbump_2_wdl_as_airtrap(path, current_vbumps)

        elif choice == "9":
            sources = input("Source CSV paths (comma separated): ").strip()
            target = input("Target CSV path: ").strip()
            src_list = [item.strip() for item in sources.split(",") if item.strip()]
            if not src_list:
                gprint("Please provide at least one source file.")
                continue
            merge(src_list, target)
            if prompt_yes_no("Load the merged result now?", True):
                current_vbumps = load_csv(target)

        elif choice == "10":
            if not current_vbumps:
                gprint("Load or create bumps first.")
                continue
            if substrate_p0 is None or substrate_p1 is None:
                gprint("Substrate box corners not set. Please enter them now.")
                substrate_p0 = prompt_point("Substrate lower corner (x, y, z)", 3)
                substrate_p1 = prompt_point("Substrate upper corner (x, y, z)", 3)
                gprint(f"Substrate box set: p0={substrate_p0}, p1={substrate_p1}")
            gprint(f"Substrate box: p0={substrate_p0}, p1={substrate_p1}")
            gprint("A plot window will open. Please CLOSE the plot window before continuing in the terminal.")
            plot_vbumps_aabb(current_vbumps, substrate_p0, substrate_p1)

        elif choice == "11":
            gprint("Set substrate box corners (as 3D points)")
            substrate_p0 = prompt_point("Substrate lower corner (x, y, z)", 3)
            substrate_p1 = prompt_point("Substrate upper corner (x, y, z)", 3)
            gprint(f"Substrate box set: p0={substrate_p0}, p1={substrate_p1}")

        elif choice == "0":
            gprint("Goodbye.")
            break

        else:
            gprint("Invalid choice, please try again.")


if __name__ == "__main__":
    main()
