# -*- coding: utf-8 -*-

"""Efficient approximation to a running median filter."""

import numpy as np


class VMedian(object):

    def __init__(self, order=1):
        '''Computes running median of a video stream'''
        self.shape = None
        self.order = order
        self._initialized = False

    def __call__(self, data):
        self.add(data)
        return self.get()

    def initialize(self, data):
        self.shape = data.shape
        self.dtype = data.dtype
        self.npts = np.product(self.shape)
        self.buffer = np.zeros((3, self.npts), dtype=data.dtype)
        self.index = 0
        if (self.order > 1):
            self.next = VMedian(order=self.order-1)
        self._initialized = False
        self._cycled = False
        self.add(data)

    def get(self, reshape=True):
        '''Returns current median image'''
        return self._result.reshape(self.shape) if reshape else self._result

    def add(self, data):
        '''Includes a new image in the median calculation'''
        if data.shape != self.shape:
            self.initialize(data)
            self._result = data.ravel()
        if self.order == 1:
            self.buffer[self.index, :] = data.ravel()
            self.index += 1
        else:
            self.next.add(data)
            if self.next.initialized:
                self.buffer[self.index, :] = self.next.get(reshape=False)
            if self.next.cycled:
                self.index += 1
        if self.index == 3:
            self.index = 0
            self._result = np.median(self.buffer, axis=0).astype(self.dtype)
            self._initialized = True
            self._cycled = True
        else:
            self._cycled = False

    def reset(self):
        self._initialized = False
        self._cycled = False
        if self.order > 1:
            self.child.reset()

    @property
    def initialized(self):
        return self._initialized

    @property
    def cycled(self):
        return self._cycled
