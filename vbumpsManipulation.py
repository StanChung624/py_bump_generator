from typing import List, Tuple
from VBumpDef import VBump

def modify_diameter(vbumps:List[VBump], new_D:float):
    for b in vbumps:
        b.D = new_D
    
def move_vbumps(selected_vbumps:List[VBump], reference_point:Tuple[float], new_point:Tuple[float], new_group:int=None, new_D:int=None, keep_origin:bool=False):
    delta_u = (new_point[0] - reference_point[0], new_point[1] - reference_point[1], new_point[2] - reference_point[2])
    ret = []
    if keep_origin:
        ret += selected_vbumps
    for vb in selected_vbumps:
        new_b = VBump(vb)+delta_u
        if new_D:
            new_b.D = new_D
        if new_group:
            new_b.group = new_group
        ret.append(new_b)
    print(f"✅ Successfully move vbumps from {reference_point} to {new_point}.")
    return ret

if __name__ == "__main__":
    from VBumpDef import to_csv
    from createRectangularArea import create_rectangular_area_XY_by_number
    from vbumps2WDL import vbump_2_wdl_as_weldline

    vbumps = create_rectangular_area_XY_by_number(
        (0,0,0), (50, 100, 0), 20, 40, 0.5, 2, 0, 1)
    
    vbump_2_wdl_as_weldline('created.wdl', vbumps)

    vbumps = move_vbumps(vbumps, (0,0,0), (50,0,0), True)

    vbump_2_wdl_as_weldline('copied.wdl', vbumps)

    to_csv("copied_vbumps.csv", vbumps)