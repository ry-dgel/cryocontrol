import fpga_cryo as fc
import spect as sp
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from functools import partial
from scanner import Scanner
from pathlib import Path

# Setup FPGA
cryo = fc.CryoFPGA()
starting_pos = {}

def init():
    starting_pos['jpe_pos'] = cryo.get_jpe_pzs()
    starting_pos['cavity_pos'] = cryo.get_cavity()
    starting_pos['galvo_pos'] = cryo.get_galvo()

def set_jpe_cav_and_count(jpe_x, jpe_y, cav_z, gal_x, gal_y):
    try:
        cryo.set_jpe_pzs(jpe_x, jpe_y, write=False)
    except ValueError:
        return 0
    cryo.set_galvo(gal_x, gal_y, write=False)
    cryo.set_cavity(cav_z, write=False)
    return cryo.just_count(5)

def progress(i,imax,pos,counts):
    print(f"{i}/{imax}, {pos} -> {counts}")

def finish(results):
    cryo.set_cavity(*starting_pos['cavity_pos'], write=False)
    cryo.set_jpe_pzs(*starting_pos['jpe_pos'], write=False)
    cryo.set_galvo(*starting_pos['galvo_pos'], write=True)
    print(np.max(results))
    
centers = [0,0,0,0,0]
spans = [1,1,1,1,1]
steps = [5,5,5,5,5]
labels = ["JPEX", "JPEY", "CAVZ", "GALX", "GALY"]
output_type = float

cavity_scan_3D = Scanner(set_jpe_cav_and_count,
                         centers, spans, steps, output_type,
                         labels=labels,
                         init = init, progress = progress, finish = finish)

results = cavity_scan_3D.run()