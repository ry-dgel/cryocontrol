from typing import DefaultDict
import dearpygui.dearpygui as dpg
import numpy as np
from time import sleep,time
from numpy.lib.histograms import histogram
from datetime import datetime
from pathlib import Path
from threading import Thread
import cryo_remote as cr
import spect
from scipy.signal import find_peaks
from scipy.constants import c

t_names = ["Platform", "Sample", "User", "Stage1", "Stage2"]
devices = {'cryo' : None, 'spect' : None}

c_thread = Thread()
wl_thread = Thread()

logs = {"pressures" : [],
        "temps"     : [],
        "lengths"   : [],
        "c_times"   : [],
        "l_times"   : []}

def start_logging(sender,app_data,user_data):

    if not dpg.get_value('logging'):
        return -1
    
    # Get cryo values
    def loop_cryo():
        while(dpg.get_value('logging')):
            sleep(dpg.get_value('cryo_cycle'))
            
            if not dpg.get_value('logging'):
                break
            update_cryo_props()

    def loop_whitelight():
        while(dpg.get_value('logging')):
            dpg.set_value("sp_status", "Sleeping")
            sleep(dpg.get_value('cryo_cycle'))
            
            if not dpg.get_value('logging'):
                break
            
            update_whitelight()

    # If we want cryo, start that
    if dpg.get_value('use_cryo'):
        t1 = Thread(target=loop_cryo)
        t1.start()

    # If we want whitelight, do~ that
    if dpg.get_value('use_whitelight'):
        t2 = Thread(target=loop_whitelight)
        t2.start()

def update_cryo_props():
    pressure = devices['cryo'].get_pressure()/1000
    temp = np.array(devices['cryo'].get_temps())
    if len(logs['c_times']) == dpg.get_value('max_pts'):
        logs["pressures"].pop(0)
        logs["temps"].pop(0)
        logs["c_times"].pop(0)
    logs["pressures"].append(pressure)
    logs["temps"].append(temp)
    logs["c_times"].append(datetime.now().timestamp())
    dpg.set_value('P',[logs["c_times"],logs["pressures"]])
    for i,name in enumerate(t_names):
        dpg.set_value(name.lower(),[logs["c_times"],[temp[i] for temp in logs["temps"]]])


# Crop out the data that we don't care about.
# Since we only care about a certain wavelength range
# and a few rows of the spectrometer camera image.
def crop_data(wl,data,wlmin,wlmax,rows):
    idxs = np.where(np.logical_and(wlmin <= wl, wl <= wlmax))[0]
    return wl[idxs], data[np.ix_(rows,idxs)]

def update_whitelight():
    dpg.set_value("sp_status", "Acquiring")
    start_time = datetime.now().timestamp()
    data = np.array(devices['spect'].get_acq()) # Get Data
    dpg.set_value("sp_status", "Fitting")
    wl = devices['spect'].get_wavelengths()
    wlc,data = crop_data(wl,data,dpg.get_value("p_min"),
                                 dpg.get_value("p_max"),
                                 [dpg.get_value("p_row")])
    if dpg.get_value('p_norm'):
        data = data/np.max(data)
    peak_wls, length = get_peaks_len(wlc,data[0],dpg.get_value('p_prominence')[:2],
                                               dpg.get_value('p_spacing'),
                                               dpg.get_value('p_width'))
    #print(dpg.get_value('WLP'))
    dpg.set_value('WLP',[peak_wls,[],[],[],[]])
    
    # Calculate Length
    dpg.set_value('WL', [wlc,data[0]])
    if len(logs['l_times']) == dpg.get_value('max_pts'):
        logs["l_times"].pop(0)
        logs["lengths"].pop(0)
    logs["l_times"].append(start_time)
    logs["lengths"].append(length)
    dpg.set_value('L',[logs["l_times"],logs["lengths"]])

def get_peaks_len(wl,counts,prom,spacing,width):
    # Get Peaks and cavity length
    peaks = find_peaks(counts,prominence=prom,
                              wlen = spacing,
                              width = width,
                              distance = spacing)
    wls = wl[peaks[0]]
    freqs = np.array([c/(wl*1E-9) for wl in wls])
    fsrs = np.abs(np.diff(freqs))

    if len(fsrs) == 0:
        return wl[0], 0
    else:
        length = np.mean([c/fsr for fsr in fsrs]) * 1E6
        return wls, length

def choose_save_dir(*args):
    chosen_dir = dpg.add_file_dialog(label="Chose Save Directory", 
                        default_path=dpg.get_value('save_dir'), 
                        directory_selector=True, modal=True,callback=set_save_dir)

def set_save_dir(sender,chosen_dir,user_data):
    dpg.set_value('save_dir',chosen_dir['file_path_name'])

def save_log(*args):
    path = Path(dpg.get_value('save_dir'))
    filename = dpg.get_value('save_file')
    stem = filename.split('.')[0]
    path_c = path / (stem+"_cryo.csv")
    path_l = path / (stem+"_length.csv")

    if len(logs["c_times"]) > 0:
        path_c.touch()
        with path_c.open('r+') as f:
            f.write("Timestamp, Pressure (mbar)" + 
                    ''.join([", " + name + " (K)" for name in t_names]) + "\n")
            for i,time in enumerate(logs["c_times"]):
                f.write(f"{time}")
                f.write(f", {logs['pressures'][i]:.2e}")
                for temp in logs["temps"][i]:
                    f.write(f", {temp:.2f}")
                f.write("\n")
    if len(logs["l_times"]) > 0:
        path_l.touch()
        with path_l.open('r+') as f:
            f.write("Timestamp, Length (um)\n")
            for i,time in enumerate(logs["l_times"]):
                f.write(f"{time}")
                f.write(f", {logs['lengths'][i]:.2f}")
                f.write("\n")

def clear_log(*args):
    logs.update({"pressures" : [],
                 "temps"     : [],
                 "lengths"   : [],
                 "c_times"   : [],
                 "l_times"   : []})

def toggle_cryo(sender,value,user):
    if value:
        try:
            devices['cryo'] = cr.CryoComm()
        except Exception as err:
                print("Failed to open connection to cryostation!")
                raise err
    else:
        del devices['cryo']
        devices['cryo'] = None

def toggle_spect(sender,value,user):
    if value:
        # Setup Spectrometer
        with dpg.window(modal=True, id='sp_warning'):
            dpg.add_text("Please wait for spectrometer to connect.",id="sp_warn")
            dpg.add_loading_indicator(id='sp_load')
        try:
            devices['spect'] = spect.Spectrometer()
        except Exception as err:
            print("Failed to open connection to spectrometer.")
        devices['spect'].vertical_bin(16)
        set_exposure()
        dpg.set_value("sp_warn", "Please wait for spectrometer to cooldown")
        devices['spect'].start_cooling()
        devices['spect'].waitfor_temp()
        dpg.set_value("sp_warn", "All done!")
        dpg.hide_item('sp_load')
        dpg.delete_item('sp_warning')
        dpg.set_value("sp_status", "Initialized")
    else:
        dpg.set_value("sp_status", "Warming")
        devices['spect'].stop_cooling()
        devices['spect'].waitfor_temp()
        devices['spect'].close()
        devices['spect'] = None
        dpg.set_value("sp_status", "Unitialized")

def set_exposure(*args):
    devices['spect'].api.SetExposureTime(dpg.get_value('exposure'))

# START DPG STUFF HERE

dpg.create_context()
dpg.create_viewport(title='Cryo Logger', width=600, height=600)

with dpg.font_registry():
    dpg.add_font(r"X:\DiamondCloud\Personal\Rigel\Scripts\FiraCode-Bold.ttf", 18, default_font=True)
    dpg.add_font(r"X:\DiamondCloud\Personal\Rigel\Scripts\FiraCode-Bold.ttf", 22, default_font=False, id="plot_font")

# Begin Menu
with dpg.window(label="Cryo Log") as main_window:
    dpg.add_text("Data Directory:")
    dpg.add_same_line()
    save_dir = dpg.add_input_text(default_value="X:\\DiamondCloud\\", id="save_dir")
    dpg.add_same_line()
    dpg.add_button(label="Pick Directory", callback=choose_save_dir)
    # Begin Tabs
    with dpg.tab_bar() as main_tabs:
        # Begin Scanner Tab
        with dpg.tab(label="Cryo"):
            # Begin  
            with dpg.child(autosize_x=True,autosize_y=True):

                with dpg.group(horizontal=True):
                    dpg.add_checkbox(label="Log",callback=start_logging, id='logging')
                    dpg.add_button(label="Clear Log", callback=clear_log, id='clear_log')

                with dpg.group(horizontal=True):
                    dpg.add_text("Filename:")
                    save_file = dpg.add_input_text(default_value="log.csv", width=200, id='save_file')
                    save_button = dpg.add_button(label="Save",callback=save_log)
                    
                with dpg.group(horizontal=True, width=-0):
                    with dpg.child(width=350,autosize_y=True,autosize_x=False):
                        dpg.add_text("Use Cryo")
                        dpg.add_same_line()
                        dpg.add_checkbox(default_value=True,id='use_cryo', callback=toggle_cryo)
                        toggle_cryo(None,True,None)

                        dpg.add_dummy()
                        dpg.add_input_float(label="Cycle Time",id='cryo_cycle', default_value=5.0)
                        dpg.add_input_int(label="Max Points", id='max_pts', min_value=0, default_value=1000000)
                        dpg.add_dummy()

                        dpg.add_text("Use Whitelight")
                        dpg.add_same_line()
                        dpg.add_checkbox(default_value=False,id='use_whitelight', callback=toggle_spect)
                        dpg.add_checkbox(label='Normalize', default_value=True, id='p_norm')
                        dpg.add_input_float(label='Exposure Time', id='exposure',
                                            default_value=10.0,min_value=0.0,max_value=1000.0,
                                            callback=set_exposure)
                        dpg.add_input_floatx(label='Prominence', size=2, id='p_prominence', default_value=[0.2,1.0], min_value = 0.0)
                        dpg.add_input_float(label='Peak Width', id='p_width', default_value=2.0, min_value=0)
                        dpg.add_input_int(label='Peak Spacing', id='p_spacing',default_value=10, min_value=0)
                        dpg.add_input_float(label="Min WL",id='p_min',default_value=598.0,min_value=0,max_value=1000)
                        dpg.add_input_float(label="Max WL",id='p_max',default_value=652.0,min_value=0,max_value=1000)
                        dpg.add_input_int(label="Binning",id='p_bin',default_value=16,min_value=0,max_value=255)
                        dpg.add_input_int(label="Row",id='p_row',default_value=8,min_value=0,max_value=255)
                        dpg.add_text("Spect. Status: ")
                        dpg.add_same_line()
                        dpg.add_text("Unitialized", id = "sp_status")

                        dpg.add_dummy(height=30)
                        with dpg.plot(no_title=True,width=-2,height=-0):
                                dpg.add_plot_axis(dpg.mvXAxis, label="Wavelength (nm)")
                                dpg.add_plot_axis(dpg.mvYAxis, label="Intensity (A.U.)", id='WL_y')
                                dpg.add_line_series([0], [0], label="WL", id='WL',
                                                    parent=dpg.last_item())
                                dpg.add_vline_series([0],id='WLP',parent='WL_y')

                    # create plot
                    with dpg.child(width=-0,autosize_y=True,autosize_x=True):
                        # Main Log Plots
                        with dpg.subplots(3,1,row_ratios=[1/3,1/3,1/3],width=-1,height=-1,link_all_x=True) as pt_subplot_id:
                            # Temperature Plot
                            with dpg.plot(no_title=True,width=-0,height=-0,id="T_plot"):
                                dpg.add_plot_axis(dpg.mvXAxis, label=None,time=True)
                                dpg.add_plot_axis(dpg.mvYAxis, label="Tempearture (K)", id="T_y_axis")
                                for name in t_names:
                                    dpg.add_line_series([datetime.now().timestamp()], [0], label=name, 
                                                            parent="T_y_axis",id=name.lower())
                                dpg.add_plot_legend()
                            # Pressure Plot
                            with dpg.plot(no_title=True,width=-0,height=-0,id="P_plot"):
                                dpg.add_plot_axis(dpg.mvXAxis, label=None,time=True)
                                dpg.add_plot_axis(dpg.mvYAxis, label="Pressure (mbar)",log_scale=True,
                                                  id="P_y_axis")
                                dpg.add_line_series([datetime.now().timestamp()], [0], label="P", 
                                                        parent=dpg.last_item(),id='P')
                            # Cavity Length Plot
                            with dpg.plot(no_title=True,width=-0,height=-0):
                                dpg.add_plot_axis(dpg.mvXAxis, label="Time",time=True)
                                dpg.add_plot_axis(dpg.mvYAxis, label="Length (um)")
                                dpg.add_line_series([datetime.now().timestamp()], [0], label="L", 
                                                        parent=dpg.last_item(),id='L')                        
       # with dpg.tab(label="Logger") as log_pane:
         #   logger = dpg_logger.mvLogger(parent=log_pane)

dpg.set_primary_window(main_window, True)

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()