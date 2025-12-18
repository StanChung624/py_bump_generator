import os
from IGSReader import ReadIGSNurbs126
from VBump.Basic import VBump, to_csv, to_hdf5, load_hdf5
from VBump.ExportWDL import vbump_2_wdl_as_weldline
from VBump.VBumpPlot import plot_vbumps


vbumps = []
files = os.listdir('./igs')
group_id = 0
layer_name_group_map = {}
# summary
summary = {}
for filename in files:
    print(f'processing {filename}...', end='', flush=True)
    centers, radiuss, layer_names = ReadIGSNurbs126('./igs/'+filename)

    for center, radius, layer_name in zip(centers, radiuss, layer_names):
        if layer_name not in layer_name_group_map:
            layer_name_group_map[layer_name] = group_id
            group_id += 1
        
        if layer_name not in summary:
            summary[layer_name] = 0
        summary[layer_name] += 1
        
        group = layer_name_group_map[layer_name]
        vbumps.append(
            VBump(x0 = center[0], y0 = center[1], z0 = center[2],
            x1 = center[0], y1 = center[1], z1 = 0.2,
            D=radius, group=group)
            )
    print('done', flush=True)

    [print(k, c) for k, c in summary.items()]


# to_csv('JYCase.csv', vbumps)
# to_hdf5('JYCase.h5', vbumps)
plot_vbumps(vbumps)
vbump_2_wdl_as_weldline('JYCase_single.wdl', vbumps)
