import cryo_remote as cr
import matplotlib.pyplot as plt
import numpy as np
import time
from datetime import timedelta
from datetime import datetime as dt
from os import path

ACQ_TIME = 10
NUM_PTS = 24 * 60 * 60 // ACQ_TIME
FNAME = "cryostation_pressure"

if __name__ == "__main__":
    
    try:
        cryo = cr.CryoComm()
    except Exception as err:
            print("Failed to open connection to cryostation!")
            raise err

    fig, axes = plt.subplots(2,1,sharex=True)
    axes[1].set_xlabel("Time Since Start (s)")
    axes[0].set_ylabel("Pressure (Torr)")
    axes[1].set_ylabel("Temperature (K)")
    
    start_time = dt.now()
    pressures = [cryo.get_pressure()/1000]
    temps = np.array([np.array(cryo.get_temps())])
    times = [0]
    filename = FNAME + start_time.strftime("_%m_%d_%H-%M-%S")
    
    prev_time = start_time
    offset = timedelta(seconds=ACQ_TIME)
    
    l, = axes[0].plot(times,pressures,marker='o')
    names = ["Platform", "Sample", "User", "Stage1", "Stage2"]
    t_lines = [axes[1].plot(times,temps[:,i],marker='x',label=names[i])[0] for i in range(len(temps[0]))]
    axes[1].legend()
    plt.show(block=False)
    with open(filename,'a') as f:
                f.write("Sec Since Start, Pressure Torr, Platform Temp, Sample Temp, User Temp, Stage 1 Temp, Stage 2 Temp\n")
    print("Acquiring %d points at %d seconds per point" % (NUM_PTS, ACQ_TIME))
    try:
        for i in range(NUM_PTS):
            with open(filename,'a') as f:
                f.write("%.2f, %.4g, %.6g, %.6g, %.6g, %.6g, %.6g\n" % (times[-1], pressures[-1], *temps[-1,:]))
            plt.pause((prev_time + offset - dt.now()).total_seconds())
            prev_time = dt.now()
            times.append((prev_time - start_time).total_seconds())
            pressures.append(cryo.get_pressure()/1000)
            temps = np.append(temps,np.array([np.array(cryo.get_temps())]),axis=0)
            
            l.set_xdata(times)
            l.set_ydata(pressures)
            for i,line in enumerate(t_lines):
                line.set_xdata(times)
                line.set_ydata(temps[:,i])
            for ax in axes:
                ax.relim()
                ax.autoscale_view()
            fig.canvas.draw_idle()
            
    except KeyboardInterrupt:
        pass
    except RuntimeError:
        pass
        
    del cryo