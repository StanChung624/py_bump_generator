from typing import Tuple
from VBumpDef import VBump, to_csv

def create_rectangular_area_XY_by_pitch(
        p0:Tuple[float], p1:Tuple[float],
        x_pitch:float, y_pitch:float,
        diameter:float, group:int,
        z:float, height:float):
    
    ret = []

    xmin = p0[0] if p0[0] < p1[0] else p1[0]
    ymin = p0[1] if p0[1] < p1[1] else p1[1]
    xmax = p0[0] if p0[0] > p1[0] else p1[0]
    ymax = p0[1] if p0[1] > p1[1] else p1[1]

    x = xmin; y = ymin

    while x < xmax:
        while y < ymax:
            ret.append(VBump()._from_setting(x,y,z,x,y,z+height,diameter,group))
            y += y_pitch
        x+=x_pitch
        y=ymin

    print(f"✅ {len(ret)}  vbumps has been created.")
    return ret

def create_rectangular_area_XY_by_number(
        p0:Tuple[float], p1:Tuple[float],
        x_num:int, y_num:int,
        diameter:float, group:int,
        z:float, height:float):
    
    x_pitch = abs(p1[0] - p0[0]) / x_num
    y_pitch = abs(p1[1] - p0[1]) / y_num
    
    new_p0, new_p1 = [0,0], [0,0]

    new_p0[0] = (p0[0] + p1[0])/2 - (x_num/2)*x_pitch
    new_p1[0] = (p0[0] + p1[0])/2 + (x_num/2)*x_pitch
    new_p0[1] = (p0[1] + p1[1])/2 - (y_num/2)*y_pitch
    new_p1[1] = (p0[1] + p1[1])/2 + (y_num/2)*y_pitch

    return create_rectangular_area_XY_by_pitch(
        new_p0, new_p1, x_pitch, y_pitch, diameter, group, z, height)

if __name__ == "__main__":

    vbumps = create_rectangular_area_XY_by_number(
        p0 = (0,0), p1= (50, 100),
        x_num=10, y_num=20,
        group=1, height=1,
        diameter= 0.15, z=0)

    to_csv("my_vbumps.csv",vbumps)