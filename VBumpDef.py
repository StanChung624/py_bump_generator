from typing import List
import csv

class VBump:
    def __init__(self, other=None):
        if other:
            self.x0 = other.x0
            self.y0 = other.y0
            self.z0 = other.z0
            self.x1 = other.x1
            self.y1 = other.y1
            self.z1 = other.z1
            self.D =  other.D
            self.group = other.group
        else:
            self.x0 = 0.
            self.y0 = 0.
            self.z0 = 0.
            self.x1 = 0.
            self.y1 = 0.
            self.z1 = 0.
            self.D = 0.
            self.group = 0

    def _from_line(self, line: str):
        splitted = line.strip().split(',')
        if len(splitted) < 7:
            raise ValueError(f"Malformed line: {line}")
        self.x0 = float(splitted[0])
        self.y0 = float(splitted[1])
        self.z0 = float(splitted[2])
        self.x1 = float(splitted[3])
        self.y1 = float(splitted[4])
        self.z1 = float(splitted[5])
        self.D = float(splitted[6])
        self.group = int(splitted[7]) if len(splitted) > 7 else 0
        return self

    def _from_setting(self, x0, y0, z0, x1, y1, z1, D, group):
        self.x0 = x0
        self.y0 = y0
        self.z0 = z0
        self.x1 = x1
        self.y1 = y1
        self.z1 = z1
        self.D = D
        self.group = group
        return self

    def __add__(self, delta: List[float]):
        # Return a new instance instead of mutating
        new_bump = VBump(self)
        new_bump.x0 += delta[0]
        new_bump.y0 += delta[1]
        new_bump.z0 += delta[2]
        new_bump.x1 += delta[0]
        new_bump.y1 += delta[1]
        new_bump.z1 += delta[2]
        return new_bump

    def __iadd__(self, delta: List[float]):
        # In-place addition: mutate this instance
        self.x0 += delta[0]
        self.y0 += delta[1]
        self.z0 += delta[2]
        self.x1 += delta[0]
        self.y1 += delta[1]
        self.z1 += delta[2]
        return self
    
    def mid_point(self):
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2, (self.z0 + self.z1) / 2)

    def p0(self):
        return (self.x0, self.y0, self.z0)

    def p1(self):
        return (self.x1, self.y1, self.z1)

def to_csv(filepath, bumps):
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write("# Virtual Bump Configuration file. Unit:mm\n")
        f.write("# x0, y0, z0, x1, y1, z1, diameter, group\n")
        writer = csv.writer(f)
        for bump in bumps:
            writer.writerow([bump.x0, bump.y0, bump.z0, bump.x1, bump.y1, bump.z1, bump.D, bump.group])
    print(f"💿 Successfully saved {len(bumps)} vbumps to {filepath}.")

def load_csv(filepath) -> List[VBump]:
    ret = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                ret.append(VBump()._from_line(line))
            except Exception as e:
                print(f"⚠️ Skipping line due to error: {e}")
    print(f"💿 Successfully loaded {len(ret)} vbumps from {filepath}.")
    return ret