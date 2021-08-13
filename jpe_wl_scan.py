from PIL.Image import SAVE
import fpga_cryo as fc
import spect

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from functools import partial
from scanner import Scanner
from pathlib import Path

SAVE_DIR = Path(r"X:\DiamondCloud\Cryostat setup\Data\2021_08_09_shorter_cavity")

def plot_data(wl, data):
    fig, axes = plt.subplots(2,1,sharex=True,gridspec_kw={'height_ratios' : [0.3,0.7]})
    
    lobj = axes[0].plot(wl,np.average(data,axis=0))[0]
    imobj = plt.imshow(data,
                       extent=[min(wl),max(wl),min(rows),max(rows)], 
                       origin="lower",
                       aspect='auto')
    cbobj = plt.colorbar()
    plt.ion()
    plt.show(block=False)
    return [fig, lobj,imobj]
    
def update_data(fig, lobj, imobj, data):
    lobj.set_ydata(np.average(data,axis=0))
    plt.gcf().axes[0].relim()
    plt.gcf().axes[0].autoscale_view(scalex=False)
    imobj.set_data(data)
    imobj.autoscale()
    fig.canvas.draw_idle()
    fig.canvas.flush_events()
    
def crop_data(wl,data,wlmin,wlmax,rows):
    idxs = np.where(np.logical_and(wlmin <= wl, wl <= wlmax))[0]
    return wl[idxs], data[np.ix_(rows,idxs)]

# Setup FPGA
cryo = fc.CryoFPGA()
starting_pos = {}

# Setup Spectrometer
andor = spect.Spectrometer()
andor._exp_time = 4
andor.api.SetExposureTime(andor._exp_time)

wl = andor.get_wavelengths()
wlmin = 545
wlmax = 675
print(andor.vertical_bin(16))
rows = [7,8,9]
data = np.array(andor.get_acq())
wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
objs = plot_data(wlc,data)
plt.pause(2)

andor.start_cooling()
andor.waitfor_temp()

def init():
    starting_pos['jpe_pos'] = cryo.get_jpe_pzs()
    starting_pos['cavity_pos'] = cryo.get_cavity()
    starting_pos['galvo_pos'] = cryo.get_galvo()
    print(starting_pos['galvo_pos'])

def jpe_z_spectra(jpe_z):
    try:
        cryo.set_jpe_pzs(0,0,jpe_z, write=True)
    except ValueError:
        return 0
    data = np.array(andor.get_acq())
    wlc, data = crop_data(wl, data, wlmin, wlmax, rows)
    return data

def progress(i,imax,pos,results):
    print(f"{i+1}/{imax}, {pos[0]}")
    update_data(*objs, results)

def finish(results, completed):
    cryo.set_jpe_pzs(*starting_pos['jpe_pos'], write=True)
    if not completed:
        print("Something went wrong, I'll keep the spectrometer cold and not close devices")
    else:
        print("Scan succesful, I'll turn off the spectrometer and close devices")
        cryo.close_fpga()
        andor.stop_cooling()
        andor.waitfor_temp()
        andor.close()
    
    
centers = [-2.5]
spans = [-5]
steps = [1300]
labels = ["JPEZ"]
output_type = object

cavity_scan_3D = Scanner(jpe_z_spectra,
                         centers, spans, steps, [], [],output_type,
                         labels=labels,
                         init = init, progress = progress)
results = cavity_scan_3D.run()
cavity_scan_3D.save_results(SAVE_DIR/'fwd_scan', as_npz=True, header=str(wlc))


spans = [5]
cavity_scan_3D_rev = Scanner(jpe_z_spectra,
                             centers, spans, steps,[],[], output_type,
                             labels=labels,
                             init = init, progress = progress, finish = finish)
results = cavity_scan_3D_rev.run()
cavity_scan_3D_rev.save_results(SAVE_DIR/'rev_scan', as_npz=True, header=str(wlc))