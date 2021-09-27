import jpe_steppers_emu as jse
import numpy as np
jse.log.setLevel(jse.logging.INFO)

try:
    stpr = jse.JPEStepper()

    print("######## INITIALIZING ########")
    user_pos,zero_pos,zeroing = stpr.read_pos_file()
    print(f"{user_pos = }")
    print(f"{zero_pos = }")
    print(f"{zeroing = }")
    stpr.initialize()
    start_pos = stpr.position
    print(f"{stpr.offset_position = }")
    print(f"{stpr.position = }")
    print(f"{stpr.clicks = }")
    print("######## MOVING Far (Clicks) ########")
    stpr.rel_lim = [110,110,110]
    stpr.lim = [[-1000,1000],[-1000,1000],[-110,0]]
    stpr.move_rel(-100,-100,-100)
    stpr.monitor_move(lambda x: print(x))
    print(f"{stpr.position = }")
    print(f"{stpr.clicks = }")
    print("######## MOVING BACK (Clicks) ########")
    stpr.move_rel(100,100,100)
    stpr.async_monitor_move(lambda x: print(x))
    print(f"{stpr.position = }")
    print(f"{stpr.clicks = }")
    print("######## MOVING Far (um) ########")
    stpr.rel_lim = [5,5,1]
    stpr.lim = [[-1000,1000],[-1000,1000],[-10,0]]

    # This should fail
    try:
        stpr.move_rel(-10,-10,-10, clicks=False)
    except ValueError as e:
        print("Succesfully didn't move outside limits")

    stpr.move_rel(-0.6,-0.6,-0.6, clicks=False)
    print(f"{stpr.position = }")
    print(f"{stpr.clicks = }")
    print("######## MOVING BACK (um) ########")
    stpr.move_rel(0.6,0.6,0.6, clicks=False)
    print(f"{stpr.position = }")
    print(f"{stpr.clicks = }")
    print("######## DEINITIALIZING ########")
    end_pos = stpr.position
    stpr.deinitialize()
    if not np.all(np.abs(end_pos-start_pos) < 1E-6):
        print("Ending position not same as starting pos!")
        print(f"Start: {start_pos}")
        print(f"End:   {end_pos}")
    else:
        print("Ending position same as starting pos!")
except Exception as e:
    stpr.deinitialize()
    raise(e)