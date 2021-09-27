import numpy as np
import logging
from jpe_coord_convert import JPECoord
from pathlib import Path
from subprocess import run
from warnings import warn
from threading import Thread


# Create root logger
log = logging.getLogger("stepper")
log.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s - %(name)s:\n\t%(message)s")
# Stream for writing all logged messages to console
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)

# Default Configuration
stp_config = {"stp_min" : -10000*0.3,   # um
              "stp_max" : 10000*0.3,    # um
              "um_per_click" : 0.3,     # um/Click
              "R": 26.0,                # mm
              "h": 58.9,                # mm
              "gain" : 100,             # Unknown
              "T" : 293,                # K
              "z_rel_lim" : 1.0,        # um
              "z_lim" : [-10,0],        # um
              "xy_rel_lim" : 5.0,       # um
              "xy_lim" : [-1000,1000],  # um
              "type" : "CA1801",        # Basically never change this
              "exe_path" : r"C:\Users\Childresslab\Documents\cacli_emulator\cacli_emulator.exe",
              "pos_path" : r"X:\DiamondCloud\Cryostat setup\Control\cryocontrol\emu_cryo_pos.csv"} 

stp_conv = JPECoord(stp_config['R'], stp_config['h'],
                    stp_config['stp_min'], stp_config['stp_max'])

class JPEStepper():

    def __init__(self, config=stp_config):
        # These set the absolute maximum positions of the stage
        # Unfortunately we can't easily zero the stage, so these
        # aren't super useful since we have no idea where the stage
        # currently is set
        self.stp_min = config['stp_min']
        self.stp_max = config['stp_max']

        # How many microns a single click of the actuator
        # encoder corresponds to, this is in the 'z' basis
        self.um_conv = config['um_per_click']

        # The parameters needed to initialize the stage, be sure
        # to set these depending on the temperature of the cryo!
        self.gain = config['gain']
        self.type = config['type']
        self.temp = config['T']

        # How far the stage can move from it's current position,
        # along each axis, in one motion step.
        self.rel_lim = np.array([config['xy_rel_lim'],
                                 config['xy_rel_lim'],
                                 config['z_rel_lim']])
        # The lower and upper bounds of absolute motion for each axis.
        self.lim = np.array([config['xy_lim'],
                             config['xy_lim'],
                             config['z_lim']])
        
        # The paths to relevant files, namely the executable that calls stage
        # commands, and where we save the position info between instances
        # of the code running.
        self.exe = config['exe_path']
        self.pos_file = Path(config['pos_path'])

        # The vectors that store the relevant zeroing and position offsets
        # As well as wether to subtract the offset for a given axis.
        # The reported position (UserPosition) is computed as: 
        #   StagePosition + OffsetPosition - (Zeroing * ZeroPosition)
        # Where: StagePosition is the position calculated from the clicks
        #        reported by the stage controller software 'cacli'
        #        
        #        OffsetPosition is set in cases where the software position and 
        #        controller position didn't match at initialization to account
        #        for the discrepency. e.g. we know we where at (10.0,10.0,10.0)
        #        and now cacli reports we were at (0.0,0.0,0.0) indicating that
        #        the controller lost power, so we set PositionOffset to 
        #        (10.0,10.0,10.0).
        # 
        #        ZeroPosition is the vector a user can safe to perform offset
        #        position measurements, say they move to (5.0,5.0,5.0) and want
        #        that to now be refered to as (0.0,0.0,5.0). We simply set
        #        the ZeroPosition to be (5.0,5.0,0) and indicate that we're using
        #        xy zeroing.
        self.offset_position = np.array([0.,0.,0.])
        self.zero_position = np.zeros(3)
        self.zeroing = [False,False]

        self.initialized = False

    def __del__(self):
        if self.initialized:
            self.deinitialize()
    
    def clicks_to_microns(self,clicks : int) -> float:
        return clicks * self.um_conv

    def microns_to_clicks(self, microns) -> int:
        return int(round(microns/self.um_conv))

    def initialize(self):
        # Initialize CACLI with current parameters
        self.cacli("initialize", self.gain, self.type, self.temp)
        # Check consistency between read and saved position
        # and update accordingly.
        user_pos, zero_pos, zeroing = self.read_pos_file()
        self.zero_position = zero_pos
        self.zeroing = zeroing
        cur_clicks = self.clicks
        cur_pos = self.position
        # Check if all values are within tolerance (~1pm)
        if not np.all((cur_pos - user_pos) < 1E-6):
            # If not, and the current clicks are all zero
            # Assume the controller has been reset and the saved
            # position is accurate, so set the offset to be the saved position
            if all([cc == 0 for cc in cur_clicks]):
                self.offset_position = user_pos
            # If it doesn't seem like the controller has been reset
            # assume there's a problem with the saved position, or we missed
            # a few steps, so set the offset to match.
            else:
                self.offset_position = user_pos - cur_pos
        self.initialized = True

    def deinitialize(self):
        # Save position to file
        # Deinitialize CACLI
        self.cacli("deinitialize")
        self.initialized = False

    def read_pos_file(self):
        """
        Example file:
            Register: User Position
            -793.384525
            -689.583077
            -7.500000
            Register: Zero Values
            756.501169
            760.263077
            8.100000
            Register: Zero status (XY/Z)
            1
            0
        """
        if not self.pos_file.exists():
            # Make the directory the file should be in
            self.pos_file.parents[0].mkdir(parents=True, exist_ok=True)
            # Make the file
            self.pos_file.touch()
            return np.array([0,0,0]), np.array([0,0,0]), [False,False]
        else:
            try:
                with self.pos_file.open() as f:
                    lines = [f.readline() for _ in range(11)]
                user_pos = [float(line.strip()) for line in lines[1:4]]
                zero_pos = [float(line.strip()) for line in lines[5:8]]
                zeroing = [bool(int(line.strip())) for line in lines[9:11]]
                return np.array(user_pos),np.array(zero_pos),np.array(zeroing)
            except ValueError:
                warn("Could not properly read position file, using all zero.")
                return np.array([0,0,0]), np.array([0,0,0]), [False,False]


    def write_pos_file(self):
        position = self.position
        zero = self.zero_position
        zeroing = self.zeroing
        #write values
        if not self.pos_file.exists():
            # Make the directory the file should be in
            self.pos_file.parents[0].mkdir(parents=True, exist_ok=True)
            # Make the file
            self.pos_file.touch()
        with self.pos_file.open('w') as f:
            f.write("Register: User Position\n")
            for pos in position:
                f.write(f"{pos}\n")
            f.write("Register: Zero Values\n")
            for zpos in zero:
                f.write(f"{zpos}\n")
            f.write("Register: Zero status (XY/Z)\n")
            for zset in zeroing:
                val = 1 if zset else 0
                f.write(f"{val}\n")

    def cacli(self, command, *args):
        commands = {"initialize"   : 'FBEN',
                    "deinitialize" : 'FBXT',
                    "set"          : 'FBCS',
                    "get"          : 'FBST',
                    "stop"         : 'FBES'}
        command = commands.get(command,command)
        string_args = [str(arg) for arg in args]
        res = run([self.exe,command] + string_args,capture_output=True)
        log.debug(f"Sending cacli message {' '.join([command] + string_args)}")
        msg = res.stdout.strip()
        msg = msg.strip().decode('UTF-8')
        if "UNAUTHORIZED COMMAND" in msg:
            warn(f"'{command}' is invalid in the current context. cacli returned '{msg}'")
        log.debug(f"Got cacli message '{msg}'")
        return msg

    def get_status(self):
        msg = self.cacli('get')
        lines = msg.splitlines()
        splits = [line.split(':') for line in lines[1:]]
        state = {split[0] : int(split[1]) for split in splits}
        return state
    
    @property
    def clicks(self):
        state = self.get_status()
        return np.array([state[name] for name in ['POS1','POS2','POS3']])

    @property
    def position(self):
        z_clicks = self.clicks
        cart_clicks = stp_conv.cart_from_zs(z_clicks)
        stage_pos = [self.clicks_to_microns(click) for click in cart_clicks]
        pos = stage_pos + self.offset_position
        zeroing = np.array([self.zeroing[0],self.zeroing[0],self.zeroing[1]],
                           dtype=int)
        pos -= zeroing * self.zero_position
        return pos

    def set_position(self,x=None,y=None,z=None):
        new_pos = [x,y,z]
        cur_pos = self.position
        new_pos = [pos if pos is not None else cur_pos[i] 
                   for i,pos in enumerate(new_pos)]
        new_pos = np.array(new_pos)
        zeroing = np.array([self.zeroing[0],self.zeroing[0],self.zeroing[1]],
                            dtype=int)
        self.enforce_limits(new_pos,cur_pos)

        # Convert from User Position to Stage Position
        new_pos += zeroing * self.zero_position
        new_stage_pos = new_pos - self.offset_position

        z_um = stp_conv.zs_from_cart(new_stage_pos)
        z_clicks = np.round(z_um/self.um_conv).astype(int)

        msg = self.cacli('set', *z_clicks)
        if msg != "STATUS : POSITION CONTROL SET":
            warn(f"Cacli returned unexpected result: {msg}")

    @property
    def error(self):
        state = self.get_status()
        return [state[name] for name in ['ERR1','ERR2','ERR3']]

    def enforce_limits(self,new_pos,cur_pos):
        axis = ['x','y','z']
        change = np.abs(np.array(new_pos) - np.array(cur_pos))
        for i, delta in enumerate(change):
            if delta > self.rel_lim[i]:
                raise ValueError((f"{axis[i]} rel position invalid. Change {delta} "
                                  f"larger than relative limit {self.rel_lim[i]}"))
        for i, pos in enumerate(new_pos):
            if not (self.lim[i][0] <= pos <= self.lim[i][1]):
                raise ValueError((f"{axis[i]} abs position invalid. Position {pos} "
                                  f"outside range {self.lim[i]}"))

    def move_rel(self,x=0.0,y=0.0,z=0.0,clicks=True):
        """
        Move a relative distance from the current position.
        x,y,z set the distance to travel in the cartesian coordinates of the stage.
        There are two ways to go about doing this, add the relative distances to the current
        position, and then set that as the new position.
        Or, calculate the number of clicks that the realtive distance is closest
        to, and add that to the current number.

        This first method has the advantage of being easier to process and 
        will give more precise movements, however it can lead to situations 
        where two relative moves (+x,+y,+z) -> (-x,-y,-z) do not result in zero net
        motion.

        The second method should ensure that moving + then - brings you back
        to the same position, but, the resulting distance moved may not be
        close to the desired amount.

        The choice of method is set by the "clicks" flag, where True
        means this second method.

        Parameters
        ----------
        x : int, optional
            Distance in microns to move along the x-axis, by default 0.0
        y : int, optional
            Distance in microns to move along the y-axis, by default 0.0
        z : int, optional
            Distance in microns to move along the z-axis, by default 0.0

        clicks : bool, optional
            Wether to round the motion to clicks before moving or not, by default True
        """
        if not clicks:
            new_pos = self.position + np.array([x,y,z])
            log.info(f"Moving {np.array([x,y,z])} um along each axis.")
        else:
            z_um = stp_conv.zs_from_cart([x,y,z])
            z_clicks = np.round(z_um/self.um_conv).astype(int)
            new_rel = stp_conv.cart_from_zs(z_clicks * self.um_conv)
            new_pos = self.position + new_rel
            log.info((f"Moving {z_clicks} clicks along each axis."
                      f"Corresponding to {new_rel} um."))

        self.set_position(*new_pos)

    def monitor_move(self, display_callback:callable = lambda *args: None, 
                           abort_callback:callable = lambda *args: False):
        prev_error = np.array([0,0,0])
        stuck_count = 0
        aborted = False
        while True:
            # Get the status of the stage
            status = self.get_status()

            # Check if we should abort motion
            if abort_callback(status):
                self.cacli('stop')
                aborted = True
                break
            
            # Display the current status
            display_callback(status)

            # Get out the current error values (clicks from setpoint).
            error = np.array([status[name] for name in ['ERR1','ERR2','ERR3']])
            # If we're not moving, break the loop, we're done
            if status['BUSY'] == 0:
                # However, if any of the errors is not zero, and we're not moving
                # something weird has happened.
                if np.any(error > 0):
                    aborted = True
                break
            
            # If we're moving, but the error isn't changing after a few loops
            # Something is up, and we should abort.
            if np.all(error == prev_error):
                stuck_count += 1
            else:
                stuck_count = 0

            if stuck_count >= 3:
                self.cacli('stop')
                aborted = True
                break

        if aborted:
            warn("Something went wrong while moving, motion aborted.")
            self.error_flag = True
            return -1

        return 0

    def async_monitor_move(self, display_callback:callable = lambda *args: None, 
                                 abort_callback:callable = lambda *args: False):
        t = Thread(target=self.monitor_move, 
                   args = (display_callback,abort_callback))
        t.start()
        return t

    def stop(self):
        self.cacli("stop")

    def set_cryotemp(self):
        self.deinitialize()
        self.gain = 300
        self.temp = 10
        self.initialize()
        log.info("Set Gain = 300, Temp = 10 for cryo operation.")

    def set_roomtemp(self):
        self.deinitialize()
        self.gain = 100
        self.temp = 293
        self.initialize()
        log.info("Set Gain = 100, Temp = 293 for RT operation.")

    @property
    def rel_lims(self):
        return self._rel_lims
    @rel_lims.setter
    def rel_lims(self,rel_lims):
        axis = ['x','y','z']
        for i, lim in rel_lims:
            if lim < 0:
                raise ValueError((f"{axis[i]} invalid relative limit {lim}. "
                                  f"Must be positive"))
        self._rel_lims = rel_lims

    @property
    def lims(self):
        return self._lims
    @lims.setter
    def lims(self, limits):
        axis = ['x','y','z']
        for i, lims in limits:
            if lims[0] > lims[1]:
                raise ValueError(f"{axis[i]} invalid limits {lims}. "
                                 f"Lower limit must be less than upper.")
        self.lims = limits

    def toggle_zero_xy(self):
        if self.zeroing[0]:
            self.zeroing[0] = False
        else:
            self.zeroing[1] = True
            self.zero_position[0] += self.position[0]
            self.zero_position[1] += self.position[1]

    def toggle_zero_z(self):
        if self.zeroing[1]:
            self.zeroing[1] = False
        else:
            self.zeroing[1] = True
            self.zero_position[2] += self.position[2]
