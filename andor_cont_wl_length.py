#%%
from re import S
import cavspy as cs
import numpy as np
import matplotlib.pyplot as plt
from scipy import constants as const
from scipy import interpolate as intp
from scipy import optimize as opt
from pathlib import Path 
from ast import literal_eval
import lmfit as lm

import spect as sp

plt.style.use(r"X:\DiamondCloud\Personal\Rigel\style_pub.mplstyle")
#%%
datafolder = Path(r"X:\DiamondCloud\Cryostat setup\Data\2022-01-18-WL_scan_test")
ref_spect_file = datafolder / "new_ref.csv"
file_index = 0
outputfolder = datafolder / f"stitch_test{file_index}"
output_file = datafolder / f"stitch_test{file_index}.csv"
# %
#fig,axes = plt.subplots(3,1)

def nm_to_THz(wl):
    return const.c/(wl*1E-9) / 1E12

def THz_to_nm(freq):
    return const.c/(freq*1E12) / 1E-9

def fit_n_gaussians(xdata,ydata,error=None,
                    nmin=2,nmax=5,
                    center=None,amp=None,sigma=None,
                    lbound = 0, ubound = np.inf,
                    tol = 1,
                    fix_c1 = True):
    n = nmin
    chisquare = np.inf
    results = None
    if error is None:
        error = np.ones_like(xdata)
    weights = 1/error
    while n <= nmax:
        if center is None:
            acenter = np.zeros(n)
        elif isinstance(center,int) or isinstance(center,float):
            acenter = np.ones(n) * center
        else:
            acenter = np.array(center)[:n] 

        if amp is None:
            aamp = np.ones(n)
        elif isinstance(amp,int) or isinstance(amp,float):
            aamp = np.ones(n) * amp
        else:
            aamp = np.array(amp)[:n]

        if sigma is None:
            asigma = np.ones(n)
        elif isinstance(sigma,int) or isinstance(sigma,float):
            asigma = np.ones(n) * sigma
        else:
            asigma = np.array(sigma)[:n]
        model = sum([lm.models.GaussianModel(prefix=f'g{i}_') for i in range(2,n+1)],
                     lm.models.GaussianModel(prefix='g1_'))
        params = model.make_params()
        for i in range(1,n+1):
            if fix_c1 and i == 1:
                params[f"g{i}_center"].set(value = acenter[i-1],min=lbound,max=ubound,vary=False)
            else:
                params[f"g{i}_center"].set(value = acenter[i-1],min=lbound,max=ubound)
            params[f"g{i}_amplitude"].set(value = aamp[i-1],min=lbound,max=ubound)
            params[f"g{i}_sigma"].set(value = asigma[i-1],min=lbound,max=ubound)
        new_results = model.fit(ydata,params=params,weights=weights,x=xdata)
        new_chisquare = new_results.chisqr
        if chisquare - new_chisquare > tol:
            chisquare = new_chisquare
            results = new_results
            n += 1
        else:
            n -= 1
            break
    #print(f"Returning fit with {n} gaussians, {chisquare = }.")
    return results, n


######################
# Reference Spectrum #
######################
#data = np.genfromtxt(ref_spect_file,skip_header=28,delimiter=',').T
data = np.genfromtxt(ref_spect_file,skip_header=1,delimiter=',').T
wl = data[0]
signal = (data[1]-min(data[1]))/np.max(data[1])
fft = np.fft.ifftshift(np.fft.ifft(signal))
ts = np.linspace(-len(fft)//2,len(fft)//2,len(fft))
cutoff = 100
fft[np.where(np.abs(ts) > cutoff)] = 0
reference_spectrum = np.fft.fft(np.fft.fftshift(fft))
model = lm.models.GaussianModel()
params = model.make_params(center=wl[np.argmax(signal)],
                            amplitude = 1,
                            sigma = 50) 
fit = model.fit(reference_spectrum,params,x=wl)
params = fit.params
# Scaled width desired
# Central Big Bump 
#shift = 0
#scale = 0.75
# Lower Bump
#shift = -48
#scale = 1.1
# Upper Bump
shift = 823 - params['center'].value
scale = 15 / params['amplitude'].value
# Highest Bump
#shift = 90
#scale = 0.95
# Two High Bumps
#shift = 800 - params['center'].value
#scale = (50/3) / params['sigma'].value
params['sigma'].value = params['sigma'].value * scale
params['center'].value = params['center'].value + shift
params['amplitude'].value = params['amplitude'].value * scale
reference_gaussian = fit.eval(x=wl,params=params)

#plt.figure()
#plt.plot(wl,reference_spectrum)
#plt.plot(wl,reference_gaussian)
#plt.show(block=False)

#Setup Spectrometer
andor = sp.Spectrometer()
andor.start_cooling()
andor.waitfor_temp()

andor.set_fvb()
andor.exp_time = 0.00001

# %%
wl = andor.get_wavelengths()
nu = np.flip(const.c/(wl*1E-9))
uniform_nu = np.linspace(min(nu),max(nu),len(nu))
timeu = np.arange(len(uniform_nu)) / (len(uniform_nu) * np.mean(np.diff(uniform_nu)))
lengthu =  (const.c * timeu[:len(timeu)//2])/2 * 1E6
newx = np.linspace(min(lengthu),max(lengthu),len(nu)*2)

# s, = axes[0].plot(uniform_nu,np.ones_like(uniform_nu))
# axes[0].secondary_xaxis('top', functions=(THz_to_nm, nm_to_THz))

# ft, = axes[1].plot(lengthu,np.ones_like(lengthu),linestyle='None',marker='o',zorder=3)
# ftmp, = axes[2].plot(lengthu,np.ones_like(lengthu),linestyle='None',marker='o',zorder=3)
# cs, = axes[2].plot(newx,np.ones_like(newx),linestyle='--',zorder=2)

# axes[0].set_ylim([-0.1,1.1])
# axes[0].set_xlabel("Frequency THz")
# axes[0].set_ylabel("WL Intensity (A.U.)")

# axes[1].set_ylabel("iFFT")

# axes[2].set_xlabel(r"Cavity Length (um)")
# axes[2].set_ylabel("iFFT - t0 Peak")


def process_data(i,time,data,index,output_file):
    data = np.array(data)
    signal = (data-min(data))/np.max(data)
    #np.savetxt(datafolder/f"raw{index}"/f"acq_{i}_{time}.csv",data)
    despectrumed_signal_wl = signal / reference_spectrum * reference_gaussian
    despectrumed_signal_wl /= np.max(despectrumed_signal_wl)
    despectrumed_signal = np.flip(despectrumed_signal_wl)

    signal_intp = intp.interp1d(nu,despectrumed_signal,'linear')
    uniform_signal = signal_intp(uniform_nu)
    #s.set_ydata(uniform_signal)

    fftu = np.abs(np.fft.ifft(uniform_signal,norm='ortho'))
    fftu = fftu[:len(fftu)//2]
    #ft.set_ydata(fftu)

    c_guess = lengthu[np.argmax(fftu[18:])+18]
    a_guess = fftu[np.argmax(fftu[18:])+18] * 4
    fitu, n = fit_n_gaussians(lengthu,fftu,
                              center=[0,c_guess*1,c_guess*2,c_guess*3,c_guess*4,c_guess*5],
                              amp =  [4,a_guess,a_guess/2,a_guess/3,a_guess/4,a_guess/5],
                              sigma = [4,4,4,4,4,4],
                              nmax=3,
                              tol = 0.01)

    zero_peak = fitu.eval_components(x=lengthu,prefix='g1_center')['g1_']

    components = fitu.eval_components(x=newx)
    #ftmp.set_ydata(fftu[:len(fftu)]-zero_peak)
    
    comps = np.zeros_like(newx)
    for key in components.keys():
        if key != 'g1_':
            comps += components[key]
    #cs.set_ydata(comps)

    center = fitu.params['g2_center'].value
    error = fitu.params['g2_center'].stderr
    with output_file.open('a') as f:
        f.write(f"{time}, {center}, {error}\n")
    print(f"{center}, chisqr = {fitu.redchi}, peaks {n = }")
    #fig.canvas.draw()
    #plt.pause(0.01)

def run_test(index):
    output_file = datafolder / f"scan_test{index}.csv"
    #raw_folder = datafolder/f"raw{index}"
    #raw_folder.mkdir(parents=True)
    with output_file.open('w') as f:
            f.write(f"time, center, error\n")
    func = lambda i,time,data: process_data(i,time,data,index,output_file)
    andor.prep_acq()
    andor.run_video(100000,func,0.1)

run_test(33)
