from time import sleep #time delay
import numpy as np
import ctypes as ct #C compatible data types

# Annoying Int Defs from the andor dll header
DRV_SUCCESS = 20002
DRV_IDLE = 20073
DRV_NOT_INITIALIZED = 20075
DRV_TEMPERATURE_STABILIZED = 20036
SHAMROCK_SUCCESS = 20202

class Spectrometer():
    def __init__(self, config_dic={}, **kwargs):

        # Default configuration and values
        config = {"_read_mode" : 4,
                  "_acq_mode"  : 1,
                  "_exp_time"  : 1.0,

                  "_h_bin"   : 1,
                  "_h_start" : 1,
                  "_h_width" : 1024,

                  "_v_bin"   : 1,
                  "_v_start" : 1,
                  "_v_width" : 256,

                  "_warm_temp" : -20,
                  "_cold_temp" : -70,

                  "_coeffs" : [535.201211,0.1265351,7.92000327e-06,-3.76483987e-09]
                 }

        # Modify config with parameters
        for key, value in config_dic.items():
            if key not in config.keys():
                print("Warning, unmatched config option: '%s' in config dictionary." % key)
                config[key] = value
        for key, value in kwargs.items():
            if key not in config.keys():
                print("Warning, unmatched config option: '%s' from kwargs." % key)
                config[key] = value
        
        for key, value in config.items():
            setattr(self,key,value)

        # Various Flags
        self.cooling = False
        self.acquiring = False
        
        # API for accessing device, from dll in andor sdk
        self.api = ct.cdll.LoadLibrary("C:\\Program Files\\Andor SDK\\Shamrock64\\atmcd64d.dll")
        self.sapi = ct.cdll.LoadLibrary("C:\\Program Files\\Andor SDK\\Shamrock64\\ShamrockCIF.dll")
        self.api.SetReadMode.argtypes = [ct.c_int]
        self.api.SetAcquisitionMode.argtypes = [ct.c_int]
        self.api.SetExposureTime.argtypes = [ct.c_float]

        # Path to directory containing detector.ini
        # Not actually needed
        # Should not be changed unless you know what you're doing.
        # Needs to be a bytes string due to conversion to C char *.
        path = b""
        print("Initializing Device, this takes a few seconds...")
        stat1 = self.api.Initialize(ct.c_char_p(path))
        stat2 = self.sapi.ShamrockInitialize(ct.c_char_p(path))
        if (stat1 == DRV_SUCCESS and stat2 == SHAMROCK_SUCCESS):
            print("Device Initialization Was Succesful!")
        else:
            raise RuntimeError("Could not Initialize a device.")
        try:
            print("Initializing Spectromemter Parameters")
            self.get_temp_range()
            self.get_sensor_size()
            self.api.SetReadMode(self._read_mode)
            self.api.SetAcquisitionMode(self._acq_mode)
            self.api.SetExposureTime(self._exp_time)
            self.set_image(self._h_bin,self._v_bin,
                           self._h_start,self._h_width,
                           self._v_start,self._v_width)
        except Exception as e:
            print("Error occured during Setup, shutting down:")
            self.api.ShutDown()
            raise(e)
        
        def __del__(self):
            self.close(force=True)
        

    ##########################
    # Acquisition Management #
    ##########################
    @property
    def exp_time(self):
        return self._exp_time
    
    @exp_time.setter
    def exp_time(self, time):
        self._exp_time = time
        self.api.SetExposureTime(self._exp_time)

    def get_sensor_size(self):
        h_pixels = ct.c_int()
        v_pixels = ct.c_int()
        self.api.GetDetector(ct.byref(h_pixels), ct.byref(v_pixels))
        self._h_pixels = h_pixels.value
        self._v_pixels = v_pixels.value
        return (self._h_pixels, self._v_pixels)
        
    def set_image(self,h_bin,v_bin,h_start,h_width,v_start,v_width):
        if h_bin > 1:
            print("Warning, recommended to keep horizontal binning at 1.")
        if (h_bin < 1 or h_bin > self._h_pixels):
            raise ValueError("Invalid Horizontal Binning: %d." % h_bin)
        self._h_bin = h_bin
        if (h_start < 1 or h_start > self._h_pixels):
            raise ValueError("Invalid Horizontal Start: %d." % h_start)
        self._h_start = h_start
        if (h_width < 1 or h_width > self._h_pixels-h_start+1):
            raise ValueError("Invalid Horizontal Width: %d." % h_width)
        if ((h_width % h_bin) != 0):
            raise ValueError("Horizontal Width must be multiple of horizontal binning.")
        self._h_width = h_width

        if (v_bin < 1 or v_bin > self._v_pixels):
            raise ValueError("Invalid Vertical Binning: %d." % v_bin)
        self._v_bin = v_bin
        if (v_start < 1 or v_start > self._v_pixels):
            raise ValueError("Invalid Vertical Start: %d." % v_start)
        self._v_start = v_start
        if (v_width < 1 or v_width > self._v_pixels-v_start+1):
            raise ValueError("Invalid Vertical Width: %d." % v_width)
        if ((v_width % v_bin) != 0):
            raise ValueError("Vertical Width must be multiple of vertical binning.")
        self._v_width = v_width

        h_end = self._h_start - 1 + self._h_width * self._h_bin
        v_end = self._v_start - 1 + self._v_width * self._v_bin
        retval =  self.api.SetImage(self._h_bin, self._v_bin, 
                                    self._h_start, h_end,
                                    self._v_start, v_end)
        return(retval)
        
    def vertical_bin(self, vbin):
        if (vbin%2):
            print("Full image vertical binning only works with a power of 2")
            print("For finer control, use set_image()")
            vbin = 1<<(vbin-1).bit_length()
            print("Setting binning to next power of 2: %d" % vbin)
        return self.set_image(1,vbin,1,1024,1,16)
        
    def get_acq(self):
        if self.get_status() != DRV_IDLE:
            raise RuntimeError("Spectrometer is not Idle")
        self.api.StartAcquisition()
        size = [self._v_width,self._h_width]
        data = (ct.c_long * (size[0] * size[1]))()
        while self.get_status() != DRV_IDLE:
            # Check again in a fraction of the exposure time
            sleep(self._exp_time/5)
        self.api.GetAcquiredData(ct.byref(data),ct.c_ulong(size[0]*size[1]))
        return np.array(data).reshape(size)

    def get_status(self):
        status = ct.c_int()
        self.api.GetStatus(ct.byref(status))
        return status.value

    ##########################
    # Temperature Management #
    ##########################
    def get_temp_range(self):
        min_temp = ct.c_int()
        max_temp = ct.c_int()
        self.api.GetTemperatureRange(ct.byref(min_temp), ct.byref(max_temp))
        self.max_temp = max_temp.value
        self.min_temp = min_temp.value

    def cap_temp(self, temp):
        if temp > self.max_temp:
            print("Warning, temperature %d > Max Temp, setting to %d." % temp, self.max_temp)
            return self.max_temp
        if temp < self.min_temp:
            print("Warning, temperature %d < Min Temp, setting to %d." % temp, self.min_temp)
            return self.min_temp
        return temp
    
    @property
    def cold_temp(self):
        return self._cold_temp

    @property
    def warm_temp(self):
        return self._warm_temp

    @cold_temp.setter
    def cold_temp(self, temp):
        temp = self.cap_temp(self,temp)
        self._cold_temp = temp
        if self.cooling:
            self.start_cooling()
    
    @warm_temp.setter
    def warm_temp(self, temp):
        temp = self.cap_temp(self,temp)
        self._warm_temp = temp
        if not self.cooling:
            self.stop_cooling()

    def get_temp(self):
        temp = ct.c_int()
        self.api.GetTemperature(ct.byref(temp))
        return temp.value

    def start_cooling(self):
        self.api.SetTemperature(self.cold_temp)
        if not self.cooling:
            self.api.CoolerON()
            self.cooling = True

    def stop_cooling(self):
        self.api.SetTemperature(self.warm_temp)
        if self.cooling:
            self.api.CoolerOFF()
            self.cooling = False

    def waitfor_temp(self):
        if self.cooling:
            target = self.cold_temp
            comp = lambda temp, target: temp >= target
            print("Cooling Down, Please Wait.")
        else:
            target = self.warm_temp
            comp = lambda temp, target: temp <= target
            print("Warming Up, Please Wait.")
        try:
            while (comp(temp := self.get_temp(),target)):
                print("",end="\r")
                print("Current Temp: %f, Target Temp: %f" % (temp,target), end="\r")
                sleep(1)
            print("")
            print("Target temperature reached!")
        except KeyboardInterrupt:
            print("")
            print("Aborting wait for temp.")
            return

    #####################
    # System Management #
    #####################
    def close(self, force=False):
        if (self.get_temp() < self.warm_temp and not force):
            raise RuntimeError("Sensor must warmup before shutting down.")
        self.api.ShutDown()
        self.sapi.ShamrockClose()
        print("Spectrometer Closed")

    ##########################
    # Wavelength Calibration #
    ##########################
    def get_wavelengths(self):
        coeffs = np.flip(np.array(self._coeffs))
        pixels = np.arange(1,1025)
        wavelengths = np.polyval(coeffs,pixels)
        wavelengths = wavelengths[self._h_start-1:self._h_start+self._h_width-1]
        if self._h_bin != 1:
            print("Warning, horionztal binning not recommended.")
            nbins = wavelengths.size//self._h_bin
            wavelengths = wavelengths.reshape(nbins,self._h_bin)
            wavelengths = np.mean(wavelengths,axis=1)
        return wavelengths

    # This is hella sketch and will likely result in a not properly calibrated
    # wavelength axis. Ideally use Andor to setup the range and 
    # get the proper calibration coeffs from there via file -> Configuration Files
    # The current coeffs are correct for wl = 596.77
    def set_central_wavelength(self, wavelength):
        current_wl = ct.c_float()
        self.sapi.ShamrockGetWavelength(0, ct.byref(current_wl))
        current_wl = current_wl.value

        diff = current_wl - self._coeffs[0]
        self._coeffs[0] = wavelength - diff

        new_wl = ct.c_float(wavelength)
        ret = self.sapi.ShamrockSetWavelength(0, new_wl)
        if ret == SHAMROCK_SUCCESS:
            return
        else:
            raise RuntimeError("Something went wrong, maybe quit and double check in Andor...")
