from typing import List
from VBump.Basic import VBump

WDL_TEMPLATE_LINES = """<Header>
Version      = 1000 
MeshName     = dummy.mfe
MaterialName = dummy.mtr
ProName      = dummy.pro
ProjectType  = 0    
</Header>

<ItemTypeInfo>
ItemTypeNumber = 2    
ItemAirTrapCount = 2    
ItemType1_MaxWLNode= 12   
ItemType2_MaxWLEdge= 8    
</ItemTypeInfo>

<ItemInfo>
ItemCount    = 2    
Item_0 = UUID(1) , ItemType(1) , Var(Weld_Meeting_Angle) , Unit(deg)
Item_1 = UUID(2) , ItemType(1) , Var(Weld_Line_Temperature) , Unit(oC)
</ItemInfo>

<MaxMinInfo>
ItemCount    = 2    
Item_0 = MAX(134.589996) , MIN(27.021999)
Item_1 = MAX(175.100006) , MIN(175.009995)
</MaxMinInfo>

<AirTrapInfo>
1      2.800000e+01  8.700000e+01  0.000000e+00
2      2.800000e+01  8.700000e+01  1.000000e+00
</AirTrapInfo>

<NodeInfo>
1      2.700000e+01  8.900001e+01  0.000000e+00
2      2.700000e+01  8.800000e+01  0.000000e+00
</NodeInfo>

<EdgeInfo>
1      2     1
</EdgeInfo>

<Item_0>
1      122
2      123
</Item_0>

<Item_1>
1      122
2      123
</Item_1>

<GlobalID>
</GlobalID>

[RESULTS WDL]
[EOF]
""".splitlines(keepends=True)

WDL_EOF = len(WDL_TEMPLATE_LINES)

class AABB:
    def __init__(self):
        self.xmin = 99999
        self.ymin = 99999
        self.zmin = 99999
        self.xmax =-99999
        self.ymax =-99999
        self.zmax =-99999
        self.D = 0
        self.group = 0

    def add(self, vbump:VBump):
        self.xmin = vbump.x0 if self.xmin > vbump.x0 else self.xmin
        self.xmin = vbump.x1 if self.xmin > vbump.x1 else self.xmin
        self.xmax = vbump.x0 if self.xmax < vbump.x0 else self.xmax
        self.xmax = vbump.x1 if self.xmax < vbump.x1 else self.xmax
        self.ymin = vbump.y0 if self.ymin > vbump.y0 else self.ymin
        self.ymin = vbump.y1 if self.ymin > vbump.y1 else self.ymin
        self.ymax = vbump.y0 if self.ymax < vbump.y0 else self.ymax
        self.ymax = vbump.y1 if self.ymax < vbump.y1 else self.ymax
        self.zmin = vbump.z0 if self.zmin > vbump.z0 else self.zmin
        self.zmin = vbump.z1 if self.zmin > vbump.z1 else self.zmin
        self.zmax = vbump.z0 if self.zmax < vbump.z0 else self.zmax
        self.zmax = vbump.z1 if self.zmax < vbump.z1 else self.zmax
        self.D = vbump.D
        self.group = vbump.group
        return self
    
    def _vertices(self):    
        return [
            (self.xmin, self.ymin, self.zmin),
            (self.xmax, self.ymin, self.zmin),
            (self.xmax, self.ymax, self.zmin),
            (self.xmin, self.ymax, self.zmin),
            (self.xmin, self.ymin, self.zmax),
            (self.xmax, self.ymin, self.zmax),
            (self.xmax, self.ymax, self.zmax),
            (self.xmin, self.ymax, self.zmax),
        ]

    def _edges(self):
        v = self._vertices()
        return [
            (v[0], v[1]), (v[1], v[2]), (v[2], v[3]), (v[3], v[0]),  
            (v[4], v[5]), (v[5], v[6]), (v[6], v[7]), (v[7], v[4]),  
            (v[0], v[4]), (v[1], v[5]), (v[2], v[6]), (v[3], v[7]) 
        ]

    def edges_as_vbumps(self)->List[VBump]:
        ret = []
        for edge in self._edges():
            ret.append(VBump.from_coords(
                edge[0][0], edge[0][1], edge[0][2], 
                edge[1][0], edge[1][1], edge[1][2],
                self.D, self.group))
        return ret
            
def _loc(block_name:str='<AirTrapInfo>'):
    c = 0
    for line in WDL_TEMPLATE_LINES:
        if block_name in line:
            return c
        c+=1

def _update_item_type_info(N_airtrap:int=2, N_vbumps:int=1):
    new_item_type_info = f"""ItemTypeNumber= 2 
ItemAirTrapCount = {N_airtrap}    
ItemType1_MaxWLNode= {N_vbumps*2+1}   
ItemType2_MaxWLEdge= {N_vbumps}    
""".splitlines(keepends=True)
    
    index = 0
    for i in range(_loc('<ItemTypeInfo>')+1, _loc('</ItemTypeInfo>')):
        WDL_TEMPLATE_LINES[i] = new_item_type_info[index]
        index+=1


def vbump_2_wdl_as_airtrap(filename:str, vbumps:List[VBump]):

    _update_item_type_info(N_airtrap=len(vbumps))

    with open(filename, 'w', encoding='utf-8') as f:
        for i in range(0,_loc('<AirTrapInfo>')+1):
            f.write(WDL_TEMPLATE_LINES[i])

        index = 1
        for vb in vbumps:
            mid_point = vb.mid_point()
            f.write(f"{index:<7d}" + f" {mid_point[0]:.6e}  "+ f" {mid_point[1]:.6e}  "+ f" {mid_point[2]:.6e}"+"\n")
            index += 1

        for i in range(_loc('</AirTrapInfo>'), WDL_EOF):
            f.write(WDL_TEMPLATE_LINES[i])
    print(f"✅ Successfully write {len(vbumps)} vbumps to file: {filename}")


def vbump_2_wdl_as_weldline(filename:str, vbumps:List[VBump]):

    _update_item_type_info(N_vbumps=len(vbumps))

    with open(filename, 'w', encoding='utf-8') as f:
        for i in range(0,_loc('<NodeInfo>')+1):
            f.write(WDL_TEMPLATE_LINES[i])

        index = 1
        for vb in vbumps:
            p = vb.p0()
            f.write(f"{index:<7d}" + f" { p[0]:.6e}  "+ f" { p[1]:.6e}  "+ f" {p[2]:.6e}"+"\n")
            index += 1
            p = vb.p1()
            f.write(f"{index:<7d}" + f" {p[0]:.6e}  "+ f" {p[1]:.6e}  "+ f" {p[2]:.6e}"+"\n")
            index += 1

        for i in range(_loc('</NodeInfo>'), _loc('<EdgeInfo>')+1):
            f.write(WDL_TEMPLATE_LINES[i])

        for i in range(1,len(vbumps)+1):
            f.write(f"{i:<7d} {i*2-1:<6d}{i*2}\n")

        for i in range(_loc('</EdgeInfo>'), _loc('<Item_0>')+1):
            f.write(WDL_TEMPLATE_LINES[i])
        
        index = 1
        for i in range(0,len(vbumps)):
            f.write(f"{index:<7d} {vbumps[i].D}\n")
            f.write(f"{index+1:<7d} {vbumps[i].D}\n")
            index+=2

        for i in range(_loc('</Item_0>'), _loc('<Item_1>')+1):
            f.write(WDL_TEMPLATE_LINES[i])
        
        index = 1
        for i in range(0,len(vbumps)):
            f.write(f"{index:<7d} {vbumps[i].group}\n")
            f.write(f"{index+1:<7d} {vbumps[i].group}\n")
            index+=2

        for i in range(_loc('</Item_1>'), WDL_EOF):
            f.write(WDL_TEMPLATE_LINES[i])

    print(f"✅ Successfully write {len(vbumps)} vbumps to file: {filename}")


def vbump_2_wdl_as_weldline_AABB(filename:str, vbumps:List[VBump]):
    new_vbumps = []
    group_vbumps = {}
    for vbump in vbumps:
        if vbump.group in group_vbumps:
            group_vbumps[vbump.group].add(vbump)
        else:
            group_vbumps[vbump.group] = AABB().add(vbump)

    for _, aabb in group_vbumps.items():
        new_vbumps += aabb.edges_as_vbumps()    
    return vbump_2_wdl_as_weldline(filename, new_vbumps)
