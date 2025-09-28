from typing import List
from VBumpDef import VBump
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

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
            ret.append(VBump()._from_setting(
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
    
def plot_vbumps_aabb(
    vbumps: List[VBump],
    substrate_p0: tuple = None,
    substrate_p1: tuple = None,
    ax: plt.Axes = None,
    has_ax: bool = True
):
    """Render AABBs for each group in vbumps using matplotlib, with legend and colored lines by group.
    Optionally, render a substrate box defined by two points (p0, p1) as a translucent gray box under all vbumps.
    """
    group_aabbs = {}
    for vb in vbumps:
        if vb.group not in group_aabbs:
            group_aabbs[vb.group] = AABB()
        group_aabbs[vb.group].add(vb)

    fig = plt.figure()
    if not ax:
        has_ax = False
        ax = fig.add_subplot(111, projection='3d')
    group_ids = sorted(group_aabbs.keys())
    cmap = plt.cm.get_cmap('tab10', len(group_ids))
    handles = []

    # Draw substrate box if provided
    if substrate_p0 is not None and substrate_p1 is not None:
        xs = [substrate_p0[0], substrate_p1[0]]
        ys = [substrate_p0[1], substrate_p1[1]]
        zs = [substrate_p0[2], substrate_p1[2]]
        verts = [
            (xs[0], ys[0], zs[0]),
            (xs[1], ys[0], zs[0]),
            (xs[1], ys[1], zs[0]),
            (xs[0], ys[1], zs[0]),
            (xs[0], ys[0], zs[1]),
            (xs[1], ys[0], zs[1]),
            (xs[1], ys[1], zs[1]),
            (xs[0], ys[1], zs[1]),
        ]
        faces = [
            [verts[0], verts[1], verts[2], verts[3]],  # bottom
            [verts[4], verts[5], verts[6], verts[7]],  # top
            [verts[0], verts[1], verts[5], verts[4]],  # front
            [verts[2], verts[3], verts[7], verts[6]],  # back
            [verts[1], verts[2], verts[6], verts[5]],  # right
            [verts[4], verts[7], verts[3], verts[0]],  # left
        ]
        substrate_poly = Poly3DCollection(
            faces, alpha=0.2, facecolor='gray', edgecolor='k', linewidths=1
        )
        ax.add_collection3d(substrate_poly)
        handles.append(plt.Line2D([0], [0], color='gray', lw=2, label='Substrate'))

    for idx, group in enumerate(group_ids):
        aabb = group_aabbs[group]
        verts = aabb._vertices()
        faces = [
            [verts[0], verts[1], verts[2], verts[3]],  # bottom
            [verts[4], verts[5], verts[6], verts[7]],  # top
            [verts[0], verts[1], verts[5], verts[4]],  # front
            [verts[2], verts[3], verts[7], verts[6]],  # back
            [verts[1], verts[2], verts[6], verts[5]],  # right
            [verts[4], verts[7], verts[3], verts[0]],  # left
        ]
        color = cmap(idx)
        poly = Poly3DCollection(faces, alpha=0.1, facecolor=color, edgecolor=color, linewidths=2)
        ax.add_collection3d(poly)
        for edge in aabb._edges():
            xs, ys, zs = zip(*edge)
            ax.plot(xs, ys, zs, color=color, linewidth=2)
        handles.append(plt.Line2D([0], [0], color=color, lw=2, label=f'Group {group}'))
        cx = (aabb.xmin + aabb.xmax) / 2
        cy = (aabb.ymin + aabb.ymax) / 2
        cz = (aabb.zmin + aabb.zmax) / 2
        ax.text(cx, cy, cz, f'{group}', color=color, fontsize=10, weight='bold')

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.title("AABB of vbumps by group")
    ax.legend(handles=handles, title="Legend")

    # Compute axis limits from all AABBs and substrate
    xs, ys, zs = [], [], []
    # Add all group AABB corners
    for aabb in group_aabbs.values():
        verts = aabb._vertices()
        xs.extend([v[0] for v in verts])
        ys.extend([v[1] for v in verts])
        zs.extend([v[2] for v in verts])
    # Add substrate corners if present
    if substrate_p0 is not None and substrate_p1 is not None:
        xs.extend([substrate_p0[0], substrate_p1[0]])
        ys.extend([substrate_p0[1], substrate_p1[1]])
        zs.extend([substrate_p0[2], substrate_p1[2]])

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)

    # Make all axes the same length (cube)
    max_range = max(x_max - x_min, y_max - y_min, z_max - z_min)
    x_mid = (x_max + x_min) / 2
    y_mid = (y_max + y_min) / 2
    z_mid = (z_max + z_min) / 2

    ax.set_xlim3d([x_mid - max_range/2, x_mid + max_range/2])
    ax.set_ylim3d([y_mid - max_range/2, y_mid + max_range/2])
    ax.set_zlim3d([z_min, z_max*5])

    if not has_ax:
        plt.show()
    

if __name__ == "__main__":
    from VBumpDef import load_csv
    vbumps = load_csv('model_Run1.vbump')
    plot_vbumps_aabb(vbumps, (0,0,0), (100,100,0))