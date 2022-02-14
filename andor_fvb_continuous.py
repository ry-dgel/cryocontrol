import spect
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from time import sleep

plt.style.use("X:/DiamondCloud/Personal/Rigel/style_pub.mplstyle")
data_folder = Path(r"X:\DiamondCloud\Cryostat setup\Data\2021-11-29_Construction_Vibrations\acq_test")
wl_file = data_folder / "wl.csv"
data_file = data_folder/"spectra.csv"

fig, axes = plt.subplots()

def plot_data(wl, data):
    lobj = axes.plot(wl,data)[0]
    plt.show(block=False)
    return lobj
    
def update_data(data, lobj,datafile):
    lobj.set_ydata(data)
    fig.canvas.draw_idle()
    fig.canvas.flush_events()
    np.savetxt(datafile,np.array([data]),delimiter=',')

def setup(spect):
    print(f"{andor.set_fvb()=}")
    andor.exp_time = 0.1
    wl = andor.get_wavelengths()
    return wl
    
def cycle_acq(spect, wl,datafile):
    data = np.array(andor.get_acq())[0,:]
    lobj = plot_data(wl,data)
    print(f"{spect.prep_acq()=}")
    try:
        while(True):
            print("Acquiring")
            data = np.array(andor.get_acq())[0,:]
            print("Acquired")
            print("Processing")
            print("Plotting")
            update_data(data,lobj,datafile)

    except KeyboardInterrupt:
        print("Exiting")
    
if __name__ == "__main__":
    andor = spect.Spectrometer()
    andor.start_cooling()
    andor.waitfor_temp()
    
    wl = setup(andor)
    data = andor.get_acq()
    with wl_file.open('wb') as f:
        np.savetxt(f,wl.T,delimiter=',')
    with data_file.open('wb') as f:
        cycle_acq(andor, wl,f)
        
    andor.stop_cooling()
    andor.waitfor_temp()
    andor.close()
    