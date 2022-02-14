from typing import DefaultDict
import dearpygui.dearpygui as dpg
import numpy as np
from time import sleep,time
from numpy.lib.histograms import histogram
import datetime
from pathlib import Path
from scanner import Scanner
from fpga_cryo import CryoFPGA
import rdpg as rdpg
dpg = rdpg.dpg

# Setup fpga control
#fpga = CryoFPGA()

def gen_point(delay = 1E-3):
    if delay >= 15E-3:
        sleep(delay)
    else:
        now = time()
        while (time() - now) < delay:
            sleep(0)
    return np.random.randn() * 100

def gen_line(n,delay=1E-3):
    return np.array([gen_point(delay) for _ in range(n)])

def gen_grid(n,m,delay=1E-3):
    return np.array([gen_line(m, delay) for _ in range(n)])

#def galvo(y,x):
#    fpga.set_galvo(x,y,write=False)
#    return fpga.just_count(dpg.get_value(ct))

def dummy_galvo(y,x):
    sleep(dpg.get_value(ct)*1E-3)
    return x**2 + y + np.random.randn()

galvo_scan = Scanner(dummy_galvo,[0,0],[1,1],[50,50],[1],[],float,['y','x'])

def start_scan(sender,app_data,user_data):
    if not dpg.get_value(scan):
        return -1
    steps = dpg.get_value(points)
    galvo_scan.steps = steps[1::-1]
    galvo_scan.centers = dpg.get_value(centers)[1::-1]
    galvo_scan.spans = dpg.get_value(spans)[1::-1]
    
    def init():
        pos = galvo_scan._get_positions()
        xmin = np.min(pos[1])
        xmax = np.max(pos[1])
        ymin = np.min(pos[0])
        ymax = np.max(pos[0])
        dpg.configure_item(heat_series_id,rows=steps[0],cols=steps[1],
                           bounds_min=(xmin,ymin),bounds_max=(xmax,ymax))
        #fpga.set_ao_wait(int(round(dpg.get_value(wt))))
    
    def abort(i,imax,idx,pos,res):
        return not dpg.get_value(scan)

    def prog(i,imax,idx,pos,res):
            dpg.set_value(pb,(i+1)/imax)
            dpg.configure_item(pb,overlay=f"{i+1}/{imax}")
            logger.log(f"Scan Running {i}")
            if not i % dpg.get_value(points)[0]: 
                plot_data = np.copy(np.flip(galvo_scan.results,0))
                dpg.set_value(heat_series_id, [plot_data,[0.0,1.0],[],[],[]])
                if dpg.get_value(auto_scale):
                    lower = np.min(plot_data)
                    upper = np.max(plot_data)
                    dpg.configure_item(colormap_id,min_scale=lower,max_scale=upper)
                    dpg.configure_item(heat_series_id,scale_min=lower,scale_max=upper)
                    dpg.set_value(line1_id,lower)
                    dpg.set_value(line2_id,upper) 
                    for ax in [heat_x,heat_y,hist_x,hist_y]:
                        dpg.fit_axis_data(ax)
                update_histogram(plot_data)

    def finish(results,completed):
        dpg.set_value(scan,False)
        if dpg.get_value(auto_save):
            save_scan()

    galvo_scan._init_func = init
    galvo_scan._abort_func = abort
    galvo_scan._prog_func = prog
    galvo_scan._finish_func = finish
    galvo_scan.run_async()

def update_histogram(data,bin_width = 10):
    nbins = max([10,int(round((np.max(data)-np.min(data))/bin_width))])
    occ,edges = np.histogram(data,bins=nbins)
    xs = [0] + list(np.repeat(occ,2)) + [0,0] 
    ys = list(np.repeat(edges,2)) + [0]
    dpg.set_value(histogram_id,[xs,ys,[],[],[]])

def set_scale(sender,app_data,user_data):
    val1 = dpg.get_value(line1_id)
    val2 = dpg.get_value(line2_id)
    lower = min([val1,val2])
    upper = max([val1,val2])
    dpg.configure_item(colormap_id,min_scale=lower,max_scale=upper)
    dpg.configure_item(heat_series_id,scale_min=lower,scale_max=upper)

def get_scan_range(*args):
    if dpg.is_plot_queried(plot_id):
        xmin,xmax,ymin,ymax = dpg.get_plot_query_area(plot_id)
        new_centers = [(xmin+xmax)/2, (ymin+ymax)/2]
        new_spans = [xmax-xmin, ymax-ymin]
        dpg.set_value(centers,new_centers)
        dpg.set_value(spans,new_spans)

def guess_time(*args):
    pts = dpg.get_value(points)
    ctime = dpg.get_value(ct) + dpg.get_value(wt)
    scan_time = pts[0] * pts[1] * ctime / 1000
    time_string = str(datetime.timedelta(seconds=scan_time))
    dpg.set_value(st,time_string)

def choose_save_dir(*args):
    chosen_dir = dpg.add_file_dialog(label="Chose Save Directory", 
                        default_path=dpg.get_value(save_dir), 
                        directory_selector=True, modal=True,callback=set_save_dir)

def set_save_dir(sender,chosen_dir,user_data):
    dpg.set_value(save_dir,chosen_dir['file_path_name'])

def save_scan(*args):
    path = Path(dpg.get_value(save_dir))
    filename = dpg.get_value(save_file)
    path /= filename
    as_npz = not (".csv" in filename)
    print(path)
    galvo_scan.save_results(str(path),as_npz=as_npz)

def cursor_drag(sender,value,user_data):
    if sender == cc:
        point = dpg.get_value(cc)[:2]
        dpg.set_value(cx,point[0])
        dpg.set_value(cy,point[1])
    if sender == cx:
        point = dpg.get_value(cc)[:2]
        point[0] = dpg.get_value(cx)
        dpg.set_value(cc,point)
    if sender == cy:
        point = dpg.get_value(cc)[:2]
        point[1] = dpg.get_value(cy)
        dpg.set_value(cc,point)
    return

#with dpg.font_registry():
#    dpg.add_font("X:\\DiamondCloud\\Personal\\Rigel\\Scripts\\FiraCode-Bold.ttf", 18, default_font=True)
#    dpg.add_font("X:\\DiamondCloud\\Personal\\Rigel\\Scripts\\FiraCode-Medium.ttf", 18, default_font=False)
#    dpg.add_font("X:\\DiamondCloud\\Personal\\Rigel\\Scripts\\FiraCode-Regular.ttf", 18, default_font=False)
#    dpg.add_font("X:\\DiamondCloud\\Personal\\Rigel\\Scripts\\FiraCode-Bold.ttf", 22, default_font=False, id="plot_font")
print("fonts")
# Begin Menu
rdpg.initialize_dpg("Confocal")
with dpg.window(tag='main_window', label="Test Window") as main_window:
    dpg.add_text("Data Directory:")
    dpg.add_same_line()
    save_dir = dpg.add_input_text(default_value="X:\\DiamondCloud\\")
    dpg.add_same_line()
    dpg.add_button(label="Pick Directory", callback=choose_save_dir)
    # Begin Tabs
    with dpg.tab_bar() as main_tabs:
        # Begin Scanner Tab
        with dpg.tab(label="Scanner"):
            # Begin  
            with dpg.child(autosize_x=True,autosize_y=True):

                with dpg.group(horizontal=True):
                    dpg.add_checkbox(label="Scan",callback=start_scan, id=scan)
                    pb = dpg.add_progress_bar(label="Scan Progress")

                with dpg.group(horizontal=True):
                    dpg.add_text("Filename:")
                    save_file = dpg.add_input_text(default_value="datafile.npz", width=200)
                    save_button = dpg.add_button(label="Save",callback=save_scan)
                    auto_save = dpg.add_checkbox(label="Auto")
                    
                with dpg.group(horizontal=True, width=0):
                    with dpg.child(width=200,autosize_y=True):
                        dpg.add_text("Autoscale")
                        dpg.add_same_line()
                        auto_scale = dpg.add_checkbox(default_value=True)
                        dpg.add_button(label="Query Scan Range",width=-1,callback=get_scan_range)
                        dpg.add_dummy()
                        dpg.add_text("Scan Settings")
                        dpg.add_text("Center (V)", indent=1)
                        centers = dpg.add_input_floatx(default_value=[-0.312965,-0.0164046],
                                                        min_value=-10.0, max_value=10.0, 
                                                        width=-1, indent=1,size=2)
                        dpg.add_text("Span (V)", indent=1)
                        spans = dpg.add_input_floatx(default_value=[1.0,1.0],min_value=-20.0, 
                                                        max_value=20.0, width=-1, indent=1,size=2)
                        dpg.add_text("Points", indent=1)
                        points = dpg.add_input_intx(default_value=[100,100],min_value=0, 
                                                    max_value=10000.0, width=-1, 
                                                    indent=1,callback=guess_time,size=2)
                        dpg.add_text("Count Time (ms)")
                        ct = dpg.add_input_float(default_value=10.0,min_value=0.0,max_value=10000.0, 
                                                    width=-1.0,step=0,callback=guess_time)
                        dpg.add_text("Wait Time (ms)")
                        wt = dpg.add_input_float(default_value=1.0,min_value=0.0,max_value=10000.0, 
                                                    width=-1,step=0,callback=guess_time)
                        dpg.add_text("Estimate Scan Time")
                        st = dpg.add_input_text(default_value="00:00:00",width=-1, readonly=True)
                        guess_time()

                    # create plot
                    with dpg.child(width=-400,autosize_y=True): 
                        with dpg.plot(label="Heat Series",width=-1,height=-1,
                                        equal_aspects=True,id=plot_id,query=True):
                            cc = dpg.add_drag_point(color=(204,36,29,122),parent=plot_id,
                                                    callback=cursor_drag,
                                                    default_value=(0.5,0.5))
                            cx = dpg.add_drag_line(color=(204,36,29,122),parent=plot_id,
                                                    callback=cursor_drag,
                                                    default_value=0.5,vertical=True)
                            cy = dpg.add_drag_line(color=(204,36,29,122),parent=plot_id,
                                                    callback=cursor_drag,
                                                    default_value=0.5,vertical=False)
                            # REQUIRED: create x and y axes
                            heat_x = dpg.add_plot_axis(dpg.mvXAxis, label="x")
                            heat_y = dpg.add_plot_axis(dpg.mvYAxis, label="y")
                            dpg.add_heat_series(np.zeros((50,50)),50,50,
                                                scale_min=0,scale_max=1000,
                                                parent=heat_y,label="heatmap",
                                                id=heat_series_id,format='',)

                    with dpg.child(width=-0,autosize_y=True):
                        dpg.add_colormap_scale(min_scale=0,max_scale=1000,
                                                width=100,height=-1,id=colormap_id)
                        dpg.add_same_line()
                        with dpg.plot(label="Histogram", width=-1,height=-1) as histogram:
                            hist_y = dpg.add_plot_axis(dpg.mvXAxis,label="Occurance")
                            hist_x = dpg.add_plot_axis(dpg.mvYAxis,label="Counts")
                            dpg.add_area_series([0],[0],parent=hist_x,
                                                fill=[120,120,120,120],id=histogram_id)
                            dpg.add_drag_line(callback=set_scale,default_value=0,
                                                parent=histogram,id=line1_id,vertical=False)
                            dpg.add_drag_line(callback=set_scale,default_value=0,
                                                parent=histogram,id=line2_id,vertical=False)
                    dpg.set_item_font(plot_id,"plot_font")
                    for wid in [colormap_id, plot_id]:
                        dpg.set_colormap(wid,dpg.mvPlotColormap_Viridis)

rdpg.start_dpg()