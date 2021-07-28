from typing import Callable
import numpy as np
from inspect import signature
from numbers import Number
from itertools import product

class Scanner():
    
    def __init__(self, function : Callable, 
                 centers : list[Number], spans: list[Number], steps : list[int],
                 n_outputs=1,
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
        self._n_out = n_outputs

        self._centers = centers
        self._spans = spans
        self._steps = steps

        self._init_func = init if init else lambda *x: None
        self._prog_func = progress if progress else lambda *x: None
        self._finish_func = finish if finish else lambda *x: None

        self._positions = self.get_positions()

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
        if len(centers) != self._n_params:
            raise RuntimeError("Number of centers doesn't match number of function parameters")
        else:
            self._centers = centers
            positions = self._get_positions

    @property
    def spans(self):
        return self._spans
    
    @spans.setter
    def spans(self, spans):
        if len(spans) != self._n_params:
            raise RuntimeError("Number of spans doesn't match number of function parameters")
        else:
            self._spans = spans
            positions = self._get_positions
    
    @property
    def steps(self):
        return self._steps
    
    @steps.setter
    def steps(self, steps):
        if len(steps) != self._n_params:
            raise RuntimeError("Number of steps doesn't match number of function parameters")
        else:
            self._steps = steps
        positions = self._get_positions

    def run(self):
        imax = np.prod(self._steps)
        if self._n_out > 1:
            results = np.zeros((self._steps + [self._n_out]))
        else:
            results = np.zeros(self._steps)
        res_iter = results.flat

        self._init_func()

        for i,position in enumerate(product(*self._positions)):
            result = self._func(*position)
            res_iter[i] = result
            self._prog_func(i, imax, position, result)
        
        self._finish_func(results)

        return results