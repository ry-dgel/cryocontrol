import fpga_cryo as fc
import spect as sp
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from scanner import Scanner
from pathlib import Path

SAVE_DIR = Path(r"X:\DiamondCloud\Cryostat setup\Data\2021_07_27_sample_in_cryo_redux")
filename = "cavity_spect_sweep"
SAVE_DIR = SAVE_DIR / filename

def plot_data(wl, data):
    fig, axes = plt.subplots(2,1,sharex=True,gridspec_kw={'height_ratios' : [0.3,0.7]})
    
    lobj = axes[0].plot(wl,np.average(data,axis=0))[0]
    imobj = plt.imshow(data,
                       extent=[min(wl),max(wl),min(rows),max(rows)], 
                       origin="lower",
                       aspect='auto')
    cbobj = plt.colorbar()
    plt.show(block=False)
    return [lobj,imobj,cbobj]
    
def update_data(data, lobj, imobj, cbobj):
    lobj.set_ydata(np.average(data,axis=0))
    plt.gcf().axes[0].relim()
    plt.gcf().axes[0].autoscale_view(scalex=False)
    imobj.set_data(data)
    imobj.autoscale()
    plt.draw()
    
def crop_data(wl,data,wlmin,wlmax,rows):
    idxs = np.where(np.logical_and(wlmin <= wl, wl <= wlmax))[0]
    return wl[idxs], data[np.ix_(rows,idxs)]

def save_data(data, voltage, index, prefix):
    path = SAVE_DIR
    title = "%sjpe_wl_scan_%d" % (prefix,index)
    filepath = os.path.join(path,title)
    with open(filepath, 'w+') as f:
        f.write("V: %f \n\n" % voltage)
        df = pd.DataFrame(data=data.transpose(), columns=["row7","row8","row9"])
        df.to_csv(f, header=True, sep=',')

def save_wl(wl):
    path = SAVE_DIR
    title = "wavelengths"
    filepath = os.path.join(path,title)
    df = pd.DataFrame(data=wl, columns=["wavelength (nm)"])
    df.to_csv(filepath, header=True, sep=',')

# Setup FPGA
cryo = fc.CryoFPGA()
galvo_pos = cryo.get_galvo()
jpe_pos = cryo.get_jpe_pzs()



# Setup Spectrometer
andor = sp.Spectrometer()
andor._exp_time = 60
andor.api.SetExposureTime(andor._exp_time)

wl = andor.get_wavelengths()
wlmin = 545
wlmax = 675
print(andor.vertical_bin(16))
rows = [7,8,9]
data = np.array(andor.get_acq())
wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
save_wl(wlc)

andor.start_cooling()
andor.waitfor_temp()

data = np.array(andor.get_acq())
wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
save_wl(wlc)
objs = plot_data(wlc,data)
save_data(data,0,-1,"Init")
plt.pause(1)