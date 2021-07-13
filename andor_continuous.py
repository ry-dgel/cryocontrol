import spect
import matplotlib.pyplot as plt
import numpy as np
from time import sleep

plt.style.use("X:/DiamondCloud/Personal/Rigel/style_pub.mplstyle")

# wlmin and wlmax defined in terms of the mirror coatings
wlmin = 580
wlmax = 620
rows = [7,8,9] #Consider only three main rows where we actually get a signal

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

def setup(spect):
    print(andor.vertical_bin(16))
    wl = andor.get_wavelengths()
    return wl
    
def cycle_acq(spect, wl):
    data = np.array(andor.get_acq())
    wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
    objs = plot_data(wlc,data)
    plt.pause(1)
    print(andor.vertical_bin(16))

    
    try:
        while(True):
            print("Acquiring")
            data = np.array(andor.get_acq())
            print("Acquired")
            print("Processing")
            wlc,data = crop_data(wl,data,wlmin,wlmax,rows)
            print("Plotting")
            update_data(data,*objs)
            plt.pause(1)
            
    except KeyboardInterrupt:
        print("Exiting")
    
if __name__ == "__main__":
    andor = spect.Spectrometer()
    andor.start_cooling()
    andor.waitfor_temp()
    
    setup(andor)
    cycle_acq(andor, wl)
        
    andor.stop_cooling()
    andor.waitfor_temp()
    andor.close()
    