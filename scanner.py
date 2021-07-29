from typing import Callable
import numpy as np
import numpy.typing as npt
from inspect import signature
from numbers import Number
from itertools import product

class Scanner():
    
    def __init__(self, function : Callable,
                 centers : list[Number], spans: list[Number], steps : list[int],
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

        self._func = function

        self._centers = np.atleast_1d(centers)
        self._spans = np.atleast_1d(spans)
        self._steps = np.atleast_1d(steps)
        self._dtype = output_dtype
        self._init_func = init if init else lambda *x: None
        self._prog_func = progress if progress else lambda *x: None
        self._finish_func = finish if finish else lambda *x: None

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
    def positions(self, positions):
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
    def centers(self, centers):
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
    def spans(self, spans):
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
    def steps(self, steps):
        steps = np.atleast_1d(steps)
        if len(steps) != self._n_params:
            raise RuntimeError("Number of steps doesn't match number of function parameters")
        else:
            self._steps = steps
        self._positions = self._get_positions()

    def run(self):
        imax = np.prod(self._steps)
        results = np.zeros(self._steps, dtype=self._dtype)
        res_iter = results.flat

        self._init_func()

        for i,position in enumerate(product(*self._positions)):
            result = self._func(*position)
            res_iter[i] = result
            self._prog_func(i, imax, position, result)
        
        self._finish_func(results)

        return results