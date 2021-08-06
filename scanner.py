from typing import Callable
import numpy as np
import numpy.typing as npt
from inspect import signature
from numbers import Number
from itertools import product
from warnings import warn
from pathlib import Path

class Scanner():
    
    def __init__(self, function : Callable,
                 centers : list[Number], spans: list[Number], steps : list[int],
                 snake : list[int] = [],
                 output_dtype: npt.DTypeLike = object,
                 labels=None,
                 init:Callable=None, 
                 progress:Callable=None, 
                 finish:Callable=None) -> None:

        self._n_params = len(signature(function).parameters)
        if len(centers) != self._n_params:
            raise RuntimeError("Number of centers doesn't match number of function parameters")
        if len(spans) != self._n_params:
            raise RuntimeError("Number of spans doesn't match number of function parameters")
        if len(steps) != self._n_params:
            raise RuntimeError("Number of steps doesn't match number of function parameters")
        if labels is not None and len(labels) != self._n_params:
            raise RuntimeError("Number of labels doesn't match number of function parameters")
        for i in snake:
            if not (0 < i <= self._n_params - 1):
                raise RuntimeError(f"Invalid axis to snake: {i}")
        self._func = function

        self._centers = np.atleast_1d(centers)
        self._spans = np.atleast_1d(spans)
        self._steps = np.atleast_1d(steps)
        self._dtype = output_dtype
        self._snake = snake
        self.labels = labels if labels else [str(i) for i in range(len(steps))]
        self._init_func = init if init else lambda *x: None
        self._prog_func = progress if progress else lambda *x: None
        self._finish_func = finish if finish else lambda *x: None

        self._has_run = False

        self._positions = self._get_positions()

    def _get_positions(self):
        positions = []
        for center,span,step in zip(self._centers,self._spans,self._steps):
            position = np.linspace(center-span/2,center+span/2,step)
            positions.append(position)
        return positions

    def _get_centers_spans(self):
        centers = []
        spans = []
        for position in self._positions:
            centers.append(np.mean(position))
            spans.append(position[-1] - position[0])
        return centers, spans

    @property
    def positions(self):
        return self._positions

    @positions.setter
    def positions(self, positions : list[list[float]]):
        positions = np.atleast_1d(positions)
        if len(positions) != self._n_params:
            raise RuntimeError("Number of positions doesn't match number of function parameters")
        else:
            self._positions = positions
        self._centers, self._spans = self._get_centers_spans()

    @property
    def centers(self):
        return self._centers
    
    @centers.setter
    def centers(self, centers : list[float]):
        centers = np.atleast_1d(centers)
        if len(centers) != self._n_params:
            raise RuntimeError("Number of centers doesn't match number of function parameters")
        else:
            self._centers = centers
            self._positions = self._get_positions()

    @property
    def spans(self):
        return self._spans
    
    @spans.setter
    def spans(self, spans : list[float]):
        spans = np.atleast_1d(spans)
        if len(spans) != self._n_params:
            raise RuntimeError("Number of spans doesn't match number of function parameters")
        else:
            self._spans = spans
            self._positions = self._get_positions()
    
    @property
    def steps(self):
        return self._steps
    
    @steps.setter
    def steps(self, steps : list[int]):
        steps = np.atleast_1d(steps)
        if len(steps) != self._n_params:
            raise RuntimeError("Number of steps doesn't match number of function parameters")
        else:
            self._steps = steps
        self._positions = self._get_positions()

    @property
    def snake(self):
        return self._snake

    @snake.setter
    def snake(self, indices : list[int]):
        for i in indices:
            if not (0 < i <= self._n_params - 1):
                raise RuntimeError(f"Invalid axis to snake: {i}")
        self._snake = indices


    def run(self):
        imax = np.prod(self._steps)
        results = np.zeros(self._steps, dtype=self._dtype)
        self.results = results
        self._has_run = True
        self._prev_positions = self.generate_scan_positions()
        res_iter = results.flat
        
        self._init_func()

        for i,position in enumerate(zip(*self._prev_positions)):
            result = self._func(*position)
            res_iter[i] = result
            self._prog_func(i, imax, position, result)
        
        self._finish_func(results)

        return results

    def save_results(self,filename,as_npz=False,header=""):
        if isinstance(filename, str):
            filename = Path(filename)
        filename = _safe_file_name(filename)
        if not self._has_run:
            raise RuntimeError("Scan must be run before saving results")

        if self._dtype is object and not as_npz:
            warn("object arrays must be saved as npz, forcing as_npz = True")
            as_npz = True

        results = self.results
        positions = self._prev_positions
        if as_npz:
            np.savez(filename, res=results, 
                               pos=np.array(positions),
                               head=np.array(header))
        
        else:
            with open(filename.with_suffix(".csv"), 'w') as f:
                f.write(header)
                f.write("\n")
                for label in self.labels:
                    f.write(f"{label}, ")
                f.write(f"value\n")
                for nindex, value in np.ndenumerate(results):
                    pos = [positions[i][idx] for i,idx in enumerate(nindex)]
                    for p in pos:
                        f.write(f"{p}, ")
                    f.write(f"{value}\n")

    def generate_scan_positions(self):
        positions = []
        
        for ax in range(self._n_params):
            n_tile = np.prod(self._steps[:ax])
            n_repeat = np.prod(self._steps[ax+1:])
            if ax in self._snake:
                pos = self._positions[ax]
                pos = np.concatenate((pos,np.flip(pos)))
                if odd_tile := n_tile % 2:
                    n_tile -= 1
                n_tile //= 2
                pos = np.tile(pos,n_tile)
                if odd_tile:
                    pos = np.concatenate((pos,self._positions[ax]))
                pos = np.repeat(pos,n_repeat)
            else:
                pos = self._positions[ax]
                pos = np.repeat(np.tile(pos,n_tile),n_repeat)
            positions.append(pos)           

        return positions   

    
def _safe_file_name(filename : Path):
    suffix = ""
    if filename.is_file():
        folder = filename.parent
        inc = len(list(folder.glob(f"{filename.stem}*")))
        return folder / f"{filename.stem}{inc}{filename.suffix}" 

