import serial as se
import numpy as np
import pyvisa as pv
from logging import getLogger
from pathlib import Path
_log = getLogger(__name__)
path = Path(__file__).parent / "devices"
rm = pv.ResourceManager()

# Serial commands with clear names
# There are more, but these should be all we need
commands = { "acceleration" : "ACC",
             "deceleration" : "DEC",
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
        self.instr = VisaInterface(port)
        self.instr.resource.write_termination = '\r'
        self.instr.resource.read_termination = '\n\r'
        self.instr.resource.baud_rate = 38600
        self.commands = commands
        self.initialize_objective_params() 

    @property
    def accel(self):
        """The accel property."""
        return self.instr.query(commands['acceleration'])
    @accel.setter
    def accel(self, value):
        self._accel = value

    @property
    def decel(self):
        """The decel property."""
        return self.instr.query(commands['deceleration'])

    @decel.setter
    def decel(self, value):
        self._decel = value

    @property
    def velocity(self):
        """The velocity property."""
        return self.instr.query(commands['velocity'])
    @velocity.setter
    def velocity(self, value):
        self._velocity = value

    @property
    def dead_band(self):
        """The dead_band property."""
        return self.instr.query(commands['dead_band'])
    @dead_band.setter
    def dead_band(self, value):
        self._dead_band = value

    @property
    def feedback(self):
        """The feedback property."""
        return self.instr.query(commands['set_feedback'])
    @feedback.setter
    def feedback(self, value):
        self._feedback = value

    @property
    def motor_power(self):
        """The motor_power property."""
        return self.instr.query(commands['set_motor'])
    @motor_power.setter
    def motor_power(self, value):
        self._motor_power = value

    @property
    def position(self):
        """The position property."""
        return self.instr.query(commands['position'])
    @position.setter
    def position(self, value):
        self._position = value

    @property
    def lower_limit(self):
        """The lower_limit property."""
        return self.instr.query(commands['soft_lower'])
    @lower_limit.setter
    def lower_limit(self, value):
        self._lower_limit = value

    @property
    def upper_limit(self):
        """The upper_limit property."""
        return self.instr.query(commands['soft_upper'])
    @upper_limit.setter
    def upper_limit(self, value):
        self._upper_limit = value

class VisaInterface():
    def __init__(self, resource_name: str) -> None:
        self.resource = rm.open_resource(resource_name)
        _model = get_id(self.resource)
        _log.debug("Opened device model: {0}".format(_model))

        config_path = configs[match_model(_model)]
        config = load_config(config_path)

        self.model = config_path.stem
        self._log = getLogger("{0}.{1}".format(__name__, self.model))
        self.commands = config.pop('commands')

        for key,entry in config.items():
            if isinstance(entry, dict):
                try:
                    config[key] = self.query(entry['command'])
                except pv.VisaIOError:
                    config[key] = entry['default']

        self.config = config

    def query(self, command:str) -> str:
        commands = parse_command(command)
        try:
            for command in commands[:-1]:
                self._log.debug("wrote {0}".format(command))
                self.resource.write(command)
            self._log.debug("wrote {0}".format(commands[-1]  + "?"))
            resp = self.resource.query(commands[-1] + "?")
            self._log.debug("recieved {0}".format(resp))
        except pv.errors.VisaIOError as e:
            self._log.error("Encountered Visa Error: \n\t\t{0}\n\tOn Query:\n\t\t{1}?".format(e,commands[-1]))
            raise e
        return resp.strip()

    def write(self, command:str) -> None:
        commands = parse_command(command)
        try:
            for command in commands:
                self._log.debug("wrote {0}".format(command))
                self.resource.write(command)
        except pv.errors.VisaIOError as e:
            self._log.error("Encountered Visa Error: \n\t\t{0}\n\tOn Write:\n\t\t{1}".format(e,commands[-1]))
            raise e

    def read(self) -> str:
        try:
            resp = self.resource.read().strip()
            self._log.debug("recieved {0}".format(resp))
            return resp
        except pv.errors.VisaIOError as e:
            self._log.error("Encountered Visa Error: \n\t\t{0}\n\tOn Read.".format(e))
            raise e

    def query_bin_data(self, command:str, **kwargs) -> np.ndarray:
        commands = parse_command(command)
        for command in commands[:-1]:
            self._log.debug("wrote {0}".format(command))
            self.resource.write(command)

        if self.config['data_width'] == 1:
            dtype = "b" # Signed char, -128 to 127
        elif self.config['data_width'] == 2:
            dtype = "h" # Signed short, -32768 to 32767
        elif self.config['data_width'] == 4:
            dtype = "i" # Signed int, -2^31 to 2^31

        self._log.debug("wrote {0}".format(commands[-1] + "?"))
        data = self.resource.query_binary_values(commands[-1]+"?", 
                                                 datatype=dtype, container=np.array,
                                                 **kwargs)
        self._log.debug("Recieved {0} values of data".format(len(data)))
        return data


def parse_command(command:str) -> list[str]:
    return list(map(lambda s: s.strip(),command.split(";")))

def get_id(inst:pv.Resource) -> str:
    try:
        identity = inst.query("*IDN?")
        return identity
    except pv.VisaIOError as e:
        _log.error("Couldn't ID requested resource! Check connections and reset.")
        raise

def load_config(path: Path) -> dict[str,object]:
    filename = path.stem

    defaults = {'commands':{}}
    if filename != "default":
        default_path = path.parent / "default.json"
        try:
            defaults = load_config(default_path)
            _log.debug("Loaded default values from %s" % default_path.as_posix())
        except FileNotFoundError:
            _log.debug("No default file found.")
            pass

    _log.debug("Loading config named: %s" % filename)
    with open(path, 'r') as f:
        try:
            config = js.load(f)
        except js.JSONDecodeError:
            _log.Error("Invalid JSON in %s" % filename)
            raise
    if 'commands' in config.keys():
        defaults['commands'].update(config.pop('commands'))
    defaults.update(config)
    return defaults

def get_configs() -> dict[str,Path]:
    configs = {}
    _log.debug("Looking for congifs in %s" % path.as_posix())
    for config_file in path.glob("**/*.json"):
        model_id = load_config(config_file)['id']
        _log.debug("Added id: %s" % model_id)
        configs[model_id] = config_file
    return configs

configs = get_configs()

def match_model(model: str) -> Path:
    match_len = 0
    match_str = ""
    sm = SequenceMatcher()
    sm.set_seq1(model)
    for model_id in configs.keys():
        sm.set_seq2(model_id)
        ml = sm.find_longest_match().size
        if ml > match_len:
            match_len = ml
            match_str = model_id
        else:
            continue
    if not match_str:
        _log.error("No matching device model found.")
        raise RuntimeError("No matching device model found.")
    _log.debug("Found best matching model ID: %s" % match_str)
    return match_str