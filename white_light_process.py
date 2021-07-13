import numpy as np
import rylab as ry
import matplotlib.pyplot as plt
from datetime import timedelta
from datetime import datetime as dt
import os

NUMACQS = 1000
WAIT_TIME = 120
FNAME = "whitelight_cavity_length"
BASE = r"X:\DiamondCloud\Cryostat setup\Data\2021_03_08_stability\Stability_tracking"
if __name__ == "__main__":
    fig, ax = plt.subplots()
    ax.set_xlabel("Time Since Start (s)")
    ax.set_ylabel("Cavity Length (um)")

    start_time = dt.now()

    logfile = FNAME + start_time.strftime("_%m_%d_%H-%M-%S") + ".csv"

    prev_time = start_time
    offset = timedelta(seconds=WAIT_TIME)
    times = []
    lengths = []

    l, = ax.plot(times, lengths, marker='o')
    plt.show(block = False)
    print("Acquiring %d points at %d seconds per point" % (NUMACQS, WAIT_TIME))
    with open(logfile,'a') as f:
        f.write("Time(s), Length(um)\n")
    for i in range(NUMACQS):
        filename = os.path.join(BASE, "whitelight%s.csv" % i)
        length = None
        while length is None:
            try:
                length, fsr = ry.cavity.white_length(filename,wlmin=600,disp=True,plot=False,dist=20, height=1500)
                if length is not None:
                    plt.close(2)
                    ry.cavity.white_length(filename,wlmin=600,disp=True,plot=True,dist=20, height=1500)
                if length is None:
                    print("Could not acquire cavity length!!!!!")
            except FileNotFoundError:
                print("File %s doesn't exist yet, waiting." % filename)
                plt.pause(5)
            except KeyboardInterrupt:
                print("Please don't itterupt while processing data.")
                pass

        print("Read file %d" % i)
        time = dt.fromtimestamp(os.path.getmtime(filename))
        times.append((time - start_time).total_seconds())
        lengths.append(length.x)
        with open(logfile,'a') as f:
            f.write("%.2f, %.4g\n" % (times[-1], lengths[-1]))

        l.set_xdata(times)
        l.set_ydata(lengths)
        ax.relim()
        ax.autoscale_view()
        fig.canvas.draw_idle()