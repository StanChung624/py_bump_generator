from typing import List
from VBump.Basic import VBump
from VBump.ExportWDL import AABB
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def plot_vbumps(
    vbumps: List[VBump],
    substrate_p0: tuple = None,
    substrate_p1: tuple = None,
    ax: plt.Axes = None
):
    """Render vbumps using matplotlib as 3D lines grouped by color.
    Optionally render a translucent substrate box.
    """
    has_ax = True
    group_vbumps = {}
    for vb in vbumps:
        group_vbumps.setdefault(vb.group, []).append(vb)

    fig = plt.figure()
    if not ax:
        has_ax = False
        ax = fig.add_subplot(111, projection='3d')

    group_ids = sorted(group_vbumps.keys())
    cmap = plt.cm.get_cmap('tab10', len(group_ids))
    handles = []

    # Draw substrate if provided
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
        substrate_poly = Poly3DCollection(faces, alpha=0.2, facecolor='gray', edgecolor='k', linewidths=1)
        ax.add_collection3d(substrate_poly)
        handles.append(plt.Line2D([0], [0], color='gray', lw=2, label='Substrate'))

    # Plot all vbumps grouped by color
    for idx, group in enumerate(group_ids):
        color = cmap(idx)
        for vb in group_vbumps[group]:
            p0 = vb.p0()
            p1 = vb.p1()
            ax.plot(
                [p0[0], p1[0]],
                [p0[1], p1[1]],
                [p0[2], p1[2]],
                color=color,
                linewidth=2
            )
        handles.append(plt.Line2D([0], [0], color=color, lw=2, label=f'Group {group}'))

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    
    if handles:
        ax.set_position([0.07, 0.1, 0.6, 0.8])
        legend_ax = ax.figure.add_axes([0.72, 0.1, 0.25, 0.8])
        legend_ax.axis('off')
        legend_ax.legend(handles=handles, title="Legend", loc='center', frameon=True)
            

    # Compute axis limits
    xs, ys, zs = [], [], []
    for vb in vbumps:
        p0, p1 = vb.p0(), vb.p1()
        xs.extend([p0[0], p1[0]])
        ys.extend([p0[1], p1[1]])
        zs.extend([p0[2], p1[2]])

    # Include substrate if provided
    if substrate_p0 is not None and substrate_p1 is not None:
        xs.extend([substrate_p0[0], substrate_p1[0]])
        ys.extend([substrate_p0[1], substrate_p1[1]])
        zs.extend([substrate_p0[2], substrate_p1[2]])

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)

    max_range = max(x_max - x_min, y_max - y_min, z_max - z_min)
    x_mid = (x_max + x_min) / 2
    y_mid = (y_max + y_min) / 2
    z_mid = (z_max + z_min) / 2

    ax.set_xlim3d([x_mid - max_range / 2, x_mid + max_range / 2])
    ax.set_ylim3d([y_mid - max_range / 2, y_mid + max_range / 2])
    ax.set_zlim3d([z_min, z_max * 5])

    if not has_ax:
        plt.show()
    
def plot_vbumps_aabb(
    vbumps: List[VBump],
    substrate_p0: tuple = None,
    substrate_p1: tuple = None,
    ax: plt.Axes = None
):
    """Render AABBs for each group in vbumps using matplotlib, with legend and colored lines by group.
    Optionally, render a substrate box defined by two points (p0, p1) as a translucent gray box under all vbumps.
    """
    has_ax = True
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

    if handles:
        ax.set_position([0.07, 0.1, 0.6, 0.8])
        legend_ax = ax.figure.add_axes([0.72, 0.1, 0.25, 0.8])
        legend_ax.axis('off')
        legend_ax.legend(handles=handles, title="Legend", loc='center', frameon=True)
    
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
    from VBump.Basic import load_csv
    vbumps = load_csv('model_Run1.vbump')
    plot_vbumps_aabb(vbumps, (0,0,0), (100,100,0))
