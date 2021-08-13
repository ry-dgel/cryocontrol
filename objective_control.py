import serial as se
import numpy as np

# Serial commands with clear names
# There are more, but these should be all we need
commands = { "acceleration" : "ACC",
             "deceleartion" : "DEC",
             "err_read_clear" : "ERR",
             "dead_band" : "DBD",
             "estop" : "EST",
             "set_feedback" : "FBK",
             "set_motor" : "MOT",
             "move_abs" : "MVA",
             "move_rel" : "MVR",
             "position" : "POS",
             "reset" : "RST",
             "stop" : "STP",
             "soft_lower" : "TLN",
             "soft_upper" : "TLP",
             "velocity" : "VEL",
             "zero" : "ZRO"
}

class Objective():
    def __init__(self, port : str = "COM3"):
        self.instr = open_visa_stuff()
        self.instr.write_termination = '\r'
        self.instr.read_termination = '\n\r'
        self.instr.baud_rate = 38600
        self.initialize_objective_params()

    @property
    def accel(self):
        """The accel property."""
        return self._accel
    @accel.setter
    def accel(self, value):
        self._accel = value

    @property
    def decel(self):
        """The decel property."""
        return self._decel
    @decel.setter
    def decel(self, value):
        self._decel = value

    @property
    def velocity(self):
        """The velocity property."""
        return self._velocity
    @velocity.setter
    def velocity(self, value):
        self._velocity = value

    @property
    def dead_band(self):
        """The dead_band property."""
        return self._dead_band
    @dead_band.setter
    def dead_band(self, value):
        self._dead_band = value

    @property
    def feedback(self):
        """The feedback property."""
        return self._feedback
    @feedback.setter
    def feedback(self, value):
        self._feedback = value

    @property
    def motor_power(self):
        """The motor_power property."""
        return self._motor_power
    @motor_power.setter
    def motor_power(self, value):
        self._motor_power = value

    @property
    def position(self):
        """The position property."""
        return self._position
    @position.setter
    def position(self, value):
        self._position = value

    @property
    def lower_limit(self):
        """The lower_limit property."""
        return self._lower_limit
    @lower_limit.setter
    def lower_limit(self, value):
        self._lower_limit = value

    @property
    def upper_limit(self):
        """The upper_limit property."""
        return self._upper_limit
    @upper_limit.setter
    def upper_limit(self, value):
        self._upper_limit = value