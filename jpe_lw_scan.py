import fpga_cryo as fc # Code for controlling cryo fpga stuff
import vipyr as vp # Library for easy oscilloscope interfacing github.com/ry-dgel/vipyr

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from time import sleep

from functools import partial
from scanner import Scanner
from pathlib import Path

from threading import Thread
from queue import Queue
from scipy.signal import find_peaks
import lmfit as lm
from scipy.constants import c
#########
# Files #
#########

# Set the save directory, and ensure it exists
SAVE_DIR = Path(r"X:\DiamondCloud\Cryostat setup\Data\2022-03-18_sample_again\lw_scan")
SAVE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_FILE_NAME = "line_width_scan"

###########
# Devices #
###########
# Setup FPGA
cryo = fc.CryoFPGA()
starting_pos = {} # For holding onto the data of where we start

# Setup scope
# Some manual setup is also required on the scope.
# Ensure that the signal is peaked at around 50% of max.
# And that the x-axis contains one sweep cycle.
scope_name = 'USB0::0x0699::0x0456::C012257::INSTR' #MDO
scope = vp.VisaScope(vp.VisaInterface(scope_name)) # Open up a vipyr Visa Scope using the above name
scope.trigger.single = True # Setup the scope to single trigger mode, i.e. stop after a single acquisition

# Setup Sig Gen
# Some manual setup is also requred on the signal generator:
# set the amplitude, scan type and frequency appropriately
# It can also be helpful to setup an external sync pulse for triggering.
sig_name = 'USB0::0x0400::0x09C4::DG1G150300137::INSTR'
# Bypass all of viyprs fancy stuff, and just open a normal pyvisa interface
sig = vp.resource_manager.open_resource(sig_name)
sig.query_delay = 0.1 # Seems like the RIGOL signal generator needs this delay

###################
# Sweep Paramters #
###################
sideband_freq = 4500 #MHz
sweep_freq = 110 #Hz
lw_ratio = 2 # Fraction of peak height to estimate linewidth. 2 Gives rough FWHM
sb_ratio = 3 # Fraction of peak height to estimate sideband positions
finesse = False # Whether to estimate finesse, set to false for just linewidth
length = 11.2E-6 # Length to use to calculate FSR for finesse
fsr = c/(2*length) / 1E6 #FSR in MHz from length

##################
# Scan Paramters #
##################
# Setup the scan, centers and spans are in volts
centers = [0,0]
spans = [30,30]
steps = [60,60]
labels = ["JPEY","JPEX"] # We're scanning in y slowly, and x quickly
output_type = object # At each point we get an array of the oscilliscope trace

####################
# Data Acquisition #
####################
# Setting up the function to be run at each point
# This first function tells the scope to start acquiring
# Since it's in single trigger mode, it'll stop once it's done
# Then, we acquire the transmission signal and push it onto the queue
def scope_get_trans_max():
    # Use the bare interface for quicker running.
    scope._interface.write(scope._commands['acq_start'])
    sleep(0.05)
    data = scope.channels[1].get_waveform(get_conv=True)
    return data

# This is the function we run at each setting
def jpe_xy_trans_scope(jpe_y,jpe_x):
    try:
        # If the x and y position are invalid, this function
        # raises a Value Error.
        # setting the z value to None makes it keep it's current setting
        # saying write=True makes the fpga immediately update the value.
        cryo.set_jpe_pzs(jpe_x,jpe_y,None, write=True)
    except fc.FPGAValueError:
        # In this case, we know it's outside the piezo scan range
        # so just do nothing
        return 0
    # Otherwise call the above function to get the max at this point.
    #return scope_get_refl_min()
    return scope_get_trans_max()

#################
# Fit Functions #
#################
def lorenz(x, amp, width, center):
    p = (x-center)/(width/2)
    return (amp) * 1/(1+p**2)

def triple_lor(x, splitting, amp, center, linewidth, ps, offset):
    shift = splitting/2
    carrier = lorenz(x, amp, linewidth, center)
    sidebands = ps * (lorenz(x, amp, linewidth, center+shift) 
                      + lorenz(x, amp, linewidth, center-shift))
    return offset + carrier + sidebands

model = lm.Model(triple_lor)

def fit_linewidth(data):
    N = len(data)
    ys = data
    xs = np.linspace(0,1,N)

    # Getting main peak
    try:
        peak=find_peaks(ys, prominence=0.4*max(data),distance=N)[0][0]
    except IndexError:
        return 0
    if peak == N:
        peak -= 1

    # Rough guessing side peaks
    lw_left = np.argmin(np.abs(ys[:peak] - np.max(ys[:peak])/lw_ratio))
    lw_right = min(len(xs)-1,len(xs) - np.argmin(np.abs(np.flip(ys[peak:]) - np.max(ys[peak:])/lw_ratio)))
    split_left = np.argmin(np.abs(ys[:peak] - np.max(ys[:peak])/sb_ratio))
    split_right = min(len(xs)-1,len(xs) - np.argmin(np.abs(np.flip(ys[peak:]) - np.max(ys[peak:])/sb_ratio)))

    # Guesses
    offset = np.min(ys)
    center = xs[peak]
    split = (xs[split_right]-xs[split_left])
    amp = max(ys) - offset
    sigma = min(np.diff(ys))
    lw = (xs[lw_right] - xs[lw_left])

    # Fitting
    params = model.make_params(splitting=split, 
                               amp=amp, 
                               center=center, 
                               linewidth=lw, 
                               ps=1/sb_ratio, 
                               offset=offset)
    
    # Computing results
    result = model.fit(ys, params, x=xs, weights = 1/sigma * np.ones(ys.size))
    chisqr = result.redchi
    best_vals = result.best_values
    # if ax is not None:
    #     ax.plot(xs, result.best_fit)
    #     if plot_init:
    #         ax.plot(xs,result.init_fit,linestyle='--',color='gray')
    #     if plot_comps:
    #         carrier = lorenz(xs, 
    #                          best_vals['amp'], best_vals['linewidth'], best_vals['center'])
    #         sidebands = best_vals['ps'] * (lorenz(xs, best_vals['amp'], best_vals['linewidth'], 
    #                                               best_vals['center']+best_vals['splitting']/2) 
    #                                       + lorenz(xs, best_vals['amp'], best_vals['linewidth'], 
    #                                                best_vals['center']-best_vals['splitting']/2))
    #         offset = np.ones_like(xs) * best_vals['offset']
    #         for comp in [carrier,sidebands,offset]:
    #             ax.plot(xs,comp,linestyle='--')

    if chisqr > 1.5:
        print("Chi-Square from triplet fit is greater than 1.5!")
        return None
    # Splitting is the distance between sidebands, and so total
    # Frequency difference is twice the modulation frequency.
    lw = best_vals['linewidth'] / best_vals['splitting'] * (2 * sideband_freq)
    if finesse:
        return fsr/np.abs(lw)
    else:
        return np.abs(lw)

# Setup the scanner object to run the above function at every point,
# the [1] sets the second axis, in this case x to be snaked, alternating
# the scan direction for every y value.
cavity_trans_scan = Scanner(jpe_xy_trans_scope,
                         centers, spans, steps, [1], [], output_type,
                         labels=labels)

# To live plot, we need a buffer to hold all the data separate from the scan
# object
data = scope.get_waveforms()
fig,ax = plt.subplots()
l, = ax.plot(data['t'],data['2'])
plt.show(block=False)
# Function to be run once at the start of the scan
def init():
    # Show the plot
    # Get the FPGAs current position for multiple objects.
    starting_pos['jpe_pos'] = cryo.get_jpe_pzs()
    starting_pos['cavity_pos'] = cryo.get_cavity()
    starting_pos['galvo_pos'] = cryo.get_galvo()
    # Print some useful info
    print("Initial FPGA Positions:")
    print(f"\tJPE: {starting_pos['jpe_pos']}")
    print(f"\tGalvo: {starting_pos['galvo_pos']}")
    # Turn on the signal generator
    sig.write("output on")
    # Pause for a bit, both for the signal generator to turn on
    # and also for the plot to have time to render.
    plt.pause(0.5)

# Function to be run after acquiring every point
def progress(i,imax,index,pos,results):
    # Print out some useful info at every point to track progress
    print(f"{i+1}/{imax}, {pos} -> Max Value: {np.max(results)}")
    print(f"\tCryo pos: {cryo.get_jpe_pzs()}")
    # Save new results to buffer array for plotting
    l.set_ydata(results)
    # Force rendering of the plot
    fig.canvas.draw_idle()
    fig.canvas.flush_events()

# Function to be run after the entire scan
def finish(results, completed):
    # Reset the jpe position to what it was at the start
    cryo.set_jpe_pzs(*starting_pos['jpe_pos'], write=True)
    # Turn off the signal generator
    sig.write("output off")
    # Check if the scan was completed, if so just close objects
    # However I haven't implemented closing visa objects.
    if not completed:
        print("Something went wrong, I won't close devices")
    else:
        print("Scan succesful, I'll close devices")
        cryo.close_fpga()

# Tell the scanner object to use these functions.
cavity_trans_scan._init_func = init
cavity_trans_scan._prog_func = progress
cavity_trans_scan._finish_func = finish
# Run the scan
thread = cavity_trans_scan.run()
# Once done, save the results as a csv, with a header.
#cavity_trans_scan.save_results(SAVE_DIR/f'{SAVE_FILE_NAME}.csv', as_npz=False, header=f"type: trans\ncenters: {centers}\nspans: {spans}\nsteps: {steps}")
cavity_trans_scan.save_results(SAVE_DIR/f'{SAVE_FILE_NAME}.npz', as_npz=True, header=f"type: trans\ncenters: {centers}\nspans: {spans}\nsteps: {steps}")

"""
cavity_trans_scan = Scanner(jpe_xy_trans_scope,
                         centers, spans, steps, [1], [], output_type,
                         labels=labels,
                         init = init, progress = progress, finish=finish)
results = cavity_trans_scan.run()
cavity_trans_scan.save_results(SAVE_DIR/'trans_scan.csv', as_npz=False, header=f"type: trans\ncenters: {centers}\nspans: {spans}\nsteps: {steps}")
"""