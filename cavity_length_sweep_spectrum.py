from numpy.core.fromnumeric import transpose
import fpga_jpe as jpe
import numpy as np
import spect as spect
import matplotlib.pyplot as plt
from time import sleep
import pandas as pd
import os

SAVE_DIR = r"X:\DiamondCloud\Cryostat setup\Data\2021_05_17_wl_full_range\Second Run"

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

if __name__=="__main__":
    stage = jpe.NiFpga()
    stage.on_activate()
    stage.set_scanner_xy_volts(-0.579695, 0.0604593)
    stage.set_scanner_

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
    save_wl(wlc)

    andor.start_cooling()
    andor.waitfor_temp()
    
    data = np.array(andor.get_acq())
    wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
    save_wl(wlc)
    objs = plot_data(wlc,data)
    save_data(data,0,-1,"Init")
    plt.pause(1)

    vmin = -3
    vmax = 0
    npts = 1500
    wait_time = 0.3
    zs = np.linspace(vmax,vmin,npts)
    zs_r = np.linspace(vmin,vmax,npts)
    V = 0
    try:
        for i,z in enumerate(zs):
            print("Acq: %d/%d" % (i+1,len(zs)))
            stage.set_scanner_z_volts(z,z,z)
            plt.pause(wait_time)
            V = z
            print("                     ",end="\r")
            print("\tAcquiring", end="\r")
            data = np.array(andor.get_acq())
            print("                     ",end="\r")
            print("                     ",end="\r")
            print("\tProcessing", end="\r")
            wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
            print("                     ",end="\r")
            print("\tPlotting", end="\r")
            update_data(data,*objs)
            save_data(data,z,i,"fwd_")
            print("                     ",end="\r")
            print("\tSaved")

        print("Reversing")
        for i,z in enumerate(zs_r):
            print("Acq: %d/%d" % (i+1,len(zs)))
            stage.set_scanner_z_volts(z,z,z)
            V = z
            print("                     ",end="\r")
            print("\tAcquiring", end="\r")
            data = np.array(andor.get_acq())
            print("                     ",end="\r")
            print("                     ",end="\r")
            print("\tProcessing", end="\r")
            wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
            print("                     ",end="\r")
            print("\tPlotting", end="\r")
            update_data(data,*objs)
            plt.pause(0.1)
            save_data(data,z,i,"rev_")
            print("                     ",end="\r")
            print("\tSaved")
    except KeyboardInterrupt:
            print("KeyboardInterrupt, Exiting")
    except IndexError:
            print("Plot Closed, Exiting")
    finally:
        #Return down to 0
        if V != 0:
            zse = np.linspace(V,0,10)
            for z in zse:
                stage.set_scanner_z_volts(z,z,z)
                sleep(0.05)

    andor.stop_cooling()
    andor.waitfor_temp()
    andor.close()
    