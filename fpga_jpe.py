# -*- coding: utf-8 -*-
"""
@author: Rigel Zifkin <rydgel.code@gmail.com>
"""

import numpy as np
from nifpga.session import Session
import time

# Functions for converting between fpga bits and volts
def _volts_to_bits(voltage):
    #TODO: I think there's an off by one error here for negative values or
    # something like that, due to two's compliments bit representation.
    if voltage == 10.0:
        return 32767
    return int(np.round(voltage * 2**15 / 10))

def _bits_to_volts(bits):
    #TODO: I think there's an off by one error here for negative values or
    # something like that, due to two's compliments bit representation.
    return int(round(bits * 10 / 2**15))

def _meters_to_volts(meters):
    #TODO: Put in proper calibration data here
    volts = meters/100E-6 * 20 - 10

    if np.abs(volts) > 10:
        print("AHHH VOLTAGE TOO HIGH")
        return 0

    return meters/100E-6 * 20 - 10

def _volts_to_meters(volts):
    #TODO: Put in proper calibration data here
    return (volts + 10)/20 * 100E-6

class NiFpga():
    """ Class that handles the NI FPGA in charge of scanning JPE Stage

    NiFpga_conf:
        module.Class: 'nifpga_conf.NiFpga'
        bitfile_path: ''
        resource_num: 'RIO0'
        clock_Frequency: 2000
        x_channel: 'AO0'
        y_channel: 'AO1'
        z_channel: 'AO2'
        counts_fifo: 'Target to Host DMA'
        # Need to send data in order to get counts back from FPGA
        pulse_pattern_fifo: 'Host to Target DMA'
        fitlogic: 'fitlogic'
    """
    _bitfile_path = 'X:\\DiamondCloud\\Fiber_proj_ctrl_softwares\\Cryo Control\\FPGA Bitfiles\\Pulsepattern(bet_FPGATarget_FPGAFULLV2_DX29Iv2+L+Y.lvbitx'
    _resource_num = "RIO0"
    _x_channel = "AO0"
    _y_channel = "AO1"
    _z1_channel = "AO5"
    _z2_channel = "AO6"
    _z3_channel = "AO7"
    _cav_channel = "A02"
    _counts_fifo = 'Target to Host DMA'
    _pulse_pattern_fifo = 'Host to Target DMA'

    def __init__(self, **kwargs):
        self._g_voltage_range = [-10,10]
        self._z_voltage_range = [-7.5,0]
        self._cav_voltage_range = [-8,8]
        self._position_range = [[0,100E-6],[0,100E-6],[0,100E-6],[0,1E-6]] #TODO: Fill in confocal ranges.
        
        # This pattern corresponds to all off, count for one tick, all off
        # Should just return 0 in the counts. Seems like the action of turning on and off triggers
        # writing of data, and so the 0s are needed
        self._count_pattern = np.array([0,131073,0], dtype="int32")
        self._move_pattern = np.array([1], dtype="int32")
        # Hardcoded clock speed of FPGA for ticks-time conversion
        self._clock_speed = 120E6

        self._scanning=False
        self._counting=False
        self._last_counts = 0
        self._count_delay = 1/30
        self._current_position = [0,0,0]
        self._clock_frequency = 1000

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        # Open the session with the FPGA card
        print("Opening fpga session")
        try:
            self._fpga = Session(bitfile=self._bitfile_path, resource=self._resource_num)
            self._fpga.reset()
        except:
            print("Couldn't create fpga session")
            raise

        # Configuring FIFO sizes #
        # TODO: Separate this out as it will have to be run every time the pulsed
        #       pattern is changed.
        # Attempt to set host->target size
        ht_size = self._fpga.fifos[self._pulse_pattern_fifo].configure(len(self._move_pattern))
        # Get returned, actual size
        print('HT Size: %d' % ht_size)
        # Let FPGA know the real size
        self._fpga.registers['H toT Size'].write(ht_size)
        # Set target->host size with true size
        self._fpga.fifos[self._pulse_pattern_fifo].configure(ht_size)
        self._fpga.registers['Wait after AO set (us)'].write(int(round(0.5/self._clock_frequency * 1E6)))
        #TODO Make this Configurable
        # Set count mode to false => no averaging
        self._fpga.registers['Counting Mode'].write(0)

        # Start the fpga vi
        self._fpga.run()
        

    def on_deactivate(self):
        """ Deactivate properly the confocal scanner dummy.
        """
        self.reset_hardware()

    def reset_hardware(self):
        """ Resets the hardware, so the connection is lost and other programs
            can access it.

        @return int: error code (0:OK, -1:error)
        """
        try:
            self._fpga.fifos[self._pulse_pattern_fifo].stop()
            self._fpga.fifos[self._counts_fifo].stop()
            self._fpga.reset()
            self._fpga.close()
        except:
            print("Could not close fpga device")
            raise
            return -1
        return 0

                        ###########################
                        #                         #
                        #   JPE Scanner Methods   #
                        #                         #
################################################################################

    def get_position_range(self):
        """ Returns the physical range of the scanner.

        @return float [4][2]: array of 4 ranges with an array containing lower
                              and upper limit
        """
        return self._position_range

    def set_position_range(self, myrange=None):
        """ Sets the physical range of the scanner.

        @param float [4][2] myrange: array of 4 ranges with an array containing
                                     lower and upper limit

        @return int: error code (0:OK, -1:error)
        """
        if myrange is None:
            myrange = [[0, 100e-6], [0, 100e-6], [0, 100e-6], [0, 1e-6]]

        if not isinstance(myrange, (frozenset, list, set, tuple, np.ndarray, )):
            print('Given range is no array type.')
            return -1

        if len(myrange) != 4:
            print('Given range should have dimension 4, but has '
                    '{0:d} instead.'.format(len(myrange)))
            return -1

        for pos in myrange:
            if len(pos) != 2:
                print('Given range limit {1:d} should have '
                        'dimension 2, but has {0:d} instead.'.format(len(pos),pos))
                return -1

            if pos[0]>pos[1]:
                print('Given range limit {0:d} has the wrong '
                        'order.'.format(pos))
                return -1

        self._position_range = myrange

        return 0

    def set_z_voltage_range(self, myrange=None):
        """ Sets the voltage range of the NI Card.

        @param float [2] myrange: array containing lower and upper limit

        @return int: error code (0:OK, -1:error)
        """
        if myrange is None:
            myrange = [-10.,10.]

        if not isinstance(myrange, (frozenset, list, set, tuple, np.ndarray, )):
            print('Given range is no array type.')
            return -1

        if len(myrange) != 2:
            print('Given range should have dimension 2, but has '
                    '{0:d} instead.'.format(len(myrange)))
            return -1

        if myrange[0]>myrange[1]:
            print('Given range limit {0:d} has the wrong '
                    'order.'.format(myrange))
            return -1

        if self.module_state() == 'locked':
            print('A Scanner is already running, close this one '
                    'first.')
            return -1

        for v in myrange:
            if abs(v) > 10:
                print('Voltage {0:d} outside hard range of +/-10V'.format(v))

        self._z_voltage_range = myrange

        return 0

    def get_z_voltage_range(self):
        return self._z_voltage_range

    def get_scanner_axes(self):
        """ Find out how many axes the scanning device is using for confocal and their names.

        @return list(str): list of axis names

        Example:
          For 3D confocal microscopy in cartesian coordinates, ['x', 'y', 'z'] is a sensible value.
          For 2D, ['x', 'y'] would be typical.
          You could build a turntable microscope with ['r', 'phi', 'z'].
          Most callers of this function will only care about the number of axes, though.

          On error, return an empty list.
        """
        return ['z1', 'z2', 'z3']

    def get_scanner_count_channels(self):
        """ Returns the list of channels that are recorded while scanning an image.

        @return list(str): channel names

        Most methods calling this might just care about the number of channels.
        """
        return ['Counts']

    def set_scanner_xy_volts(self, x: float, y: float) -> int:
        """Move galvo to x, y.

        @param float x: voltage in x-direction
        @param float y: voltage in y-direction

        @return int: error code (0:OK, -1:error)
        """
        for v in [x,y]:
            if v < min(self._g_voltage_range) or v > max(self._g_voltage_range):
                print("Given voltage outside safe range")
                return -1
        try:
            self._fpga.registers['Start FPGA 1'].write(0)
            self._fpga.registers[self._x_channel].write(_volts_to_bits(x))
            self._fpga.registers[self._y_channel].write(_volts_to_bits(y))
            try:
                #self._fpga.fifos[self._counts_fifo].stop()
                self._fpga.fifos[self._pulse_pattern_fifo].stop()
                self._fpga.fifos[self._pulse_pattern_fifo].write(self._move_pattern,5000)
            except:
                print("Timed out while writing pulse pattern to FPGA")
                raise

            # Query fpga status until it's done pulsing and counting.
            self._fpga.registers['Start FPGA 1'].write(1)
            for i in range(20): # Limit to 20 loops
                if not self._fpga.registers['Start FPGA 1'].read():
                    break
                else:
                    time.sleep(0.5/self._clock_frequency)
            else: # This only runs if for loop finishes without break
                raise TimeoutError

        except:
            print("Could not set position on fpga device")
            raise
            return -1

        return 0

    def set_scanner_z_volts(self, z1, z2, z3):
        """Move stage to z1, z2, z3.

        @param float z: voltage in z-direction

        @return int: error code (0:OK, -1:error)
        """
        for z in [z1,z2,z3]:
            if z < min(self._z_voltage_range) or z > max(self._z_voltage_range):
                print("Given Z voltage outside safe range")
                return -1
        try:
            self._fpga.registers['Start FPGA 1'].write(0)
            self._fpga.registers[self._z1_channel].write(_volts_to_bits(z1))
            self._fpga.registers[self._z2_channel].write(_volts_to_bits(z2))
            self._fpga.registers[self._z3_channel].write(_volts_to_bits(z3))
            try:
                #self._fpga.fifos[self._counts_fifo].stop()
                self._fpga.fifos[self._pulse_pattern_fifo].stop()
                self._fpga.fifos[self._pulse_pattern_fifo].write(self._move_pattern,5000)
            except:
                print("Timed out while writing pulse pattern to FPGA")
                raise

            # Query fpga status until it's done pulsing and counting.
            self._fpga.registers['Start FPGA 1'].write(1)
            for i in range(20): # Limit to 20 loops
                if not self._fpga.registers['Start FPGA 1'].read():
                    break
                else:
                    time.sleep(0.5/self._clock_frequency)
            else: # This only runs if for loop finishes without break
                raise TimeoutError

        except:
            print("Could not set position on fpga device")
            raise
            return -1

        return 0

    def get_scanner_z_volts(self):
        """ Get the current position of the scanner hardware.

        @return float[n]: current position in (z1,z3,z3).
        """
        try:
            z1 = _bits_to_volts(self._fpga.registers[self._z1_channel].read())
            z2 = _bits_to_volts(self._fpga.registers[self._z2_channel].read())
            z3 = _bits_to_volts(self._fpga.registers[self._z3_channel].read())
        except:
            print("Could not read position on fpga device")
            raise
            return [-1.0,-1.0,-1.0,-1.0]

        return [z1,z2,z3]

    def set_cavity_z_volts(self, cav,):
        """Move stage to z1, z2, z3.

        @param float z: voltage in z-direction

        @return int: error code (0:OK, -1:error)
        """
        for z in [cav]:
            if z < min(self._cav_voltage_range) or z > max(self._cav_voltage_range):
                print("Given Z voltage outside safe range")
                return -1
        try:
            self._fpga.registers['Start FPGA 1'].write(0)
            self._fpga.registers[self._cav_channel].write(_volts_to_bits(cav))
            try:
                #self._fpga.fifos[self._counts_fifo].stop()
                self._fpga.fifos[self._pulse_pattern_fifo].stop()
                self._fpga.fifos[self._pulse_pattern_fifo].write(self._move_pattern,5000)
            except:
                print("Timed out while writing pulse pattern to FPGA")
                raise

            # Query fpga status until it's done pulsing and counting.
            self._fpga.registers['Start FPGA 1'].write(1)
            for i in range(20): # Limit to 20 loops
                if not self._fpga.registers['Start FPGA 1'].read():
                    break
                else:
                    time.sleep(0.5/self._clock_frequency)
            else: # This only runs if for loop finishes without break
                raise TimeoutError

        except:
            print("Could not set position on fpga device")
            raise
            return -1

        return 0

    def get_cavity_z_volts(self):
        """ Get the current position of the scanner hardware.

        @return float[n]: current position in (cav).
        """
        try:
            z1 = _bits_to_volts(self._fpga.registers[self._cav_channel].read())
        except:
            print("Could not read position on fpga device")
            raise
            return [-1.0]

        return z1

    def close_scanner(self):
        """ Closes the scanner and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        try:
            self._scanning = False
            self._fpga.fifos[self._counts_fifo].stop()
            self._fpga.fifos[self._pulse_pattern_fifo].stop()
        except:
            print("Couldn't Stop FIFOs")
            raise
            return -1
        return 0
