from typing import Callable
import numpy as np
from inspect import signature
from numbers import Number

class Scanner():
    
    def __init__(self, function : Callable, 
                 centers : list[Number], spans: list[Number], steps : list[int],
                 labels=None,
                 init:Callable=None, 
                 progress:Callable=None, 
                 cleanup:Callable=None) -> None:

        self._n_params = len(signature(function).parameters)
        if len(centers) != self._n_params:
            raise RuntimeError("Number of centers doesn't match number of function paramters")
        if len(spans) != self._n_params:
            raise RuntimeError("Number of spans doesn't match number of function paramters")
        if len(steps) != self._n_params:
             raise RuntimeError("Number of steps doesn't match number of function paramters")
        if labels is not None and len(labels) != self._n_params:
            raise RuntimeError("Number of labels doesn't match number of function parameters")

        self._func = function
        self._centers = centers
        self._spans = spans
        self._steps = steps
        self._init_func = init
        self._prog_func = progress
        self._clean_func = cleanup

    def get_positions(self):
        positions = []
        for center,span,step in zip(self.centers,self.spans,self.steps):
            position = np.linspace(center-span/2,center+span/2,step)
            positions.append(position)
        return positions
