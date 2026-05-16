'''ROI crop filter and companion Qt widget.'''
from qtpy import QtCore, QtWidgets
from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
from pyqtgraph import SpinBox
from QVideo.lib.videotypes import Image


__all__ = ['ROIFilter', 'QROIFilter']


class ROIFilter(VideoFilter):

    '''Crop video frames to a rectangular region of interest.

    The ROI is defined by its top-left corner ``(x, y)`` and its
    ``(w, h)`` dimensions.  When the frame shape is first seen — or
    whenever it changes — the ROI is clamped to fit within the frame.
    That check costs a single tuple comparison per frame; the clamp
    itself runs only on shape changes.

    Parameters
    ----------
    x : int
        Column offset of the left edge of the ROI.  Default: ``0``.
    y : int
        Row offset of the top edge of the ROI.  Default: ``0``.
    w : int
        Width of the ROI in pixels.  Default: ``128``.
    h : int
        Height of the ROI in pixels.  Default: ``128``.
    '''

    def __init__(self,
                 x: int = 0,
                 y: int = 0,
                 w: int = 128,
                 h: int = 128) -> None:
        super().__init__()
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def _clamp(self, shape: tuple) -> None:
        rows, cols = shape[:2]
        self._x = min(self._x, cols - 1)
        self._y = min(self._y, rows - 1)
        self._w = min(self._w, cols - self._x)
        self._h = min(self._h, rows - self._y)

    def add(self, image: Image) -> None:
        if self.data is None or image.shape[:2] != self.data.shape[:2]:
            self._clamp(image.shape)
        super().add(image)

    def to_code(self) -> 'FilterCode':
        from QVideo.lib.QVideoFilter import FilterCode
        x, y, w, h = int(self._x), int(self._y), int(self._w), int(self._h)
        return FilterCode(
            imports=frozenset(),
            lines=[f'image = image[{y}:{y + h}, {x}:{x + w}]'],
            comment=f'ROI crop: x={x}, y={y}, w={w}, h={h}',
        )

    def get(self) -> Image:
        '''Crop the current frame to the ROI bounds and return it.

        Returns
        -------
        Image
            Cropped frame.
        '''
        if self.data is None:
            raise ValueError('no data to crop')
        return self.data[int(self.y):int(self.y + self.h),
                         int(self.x):int(self.x + self.w)]

    @property
    def x(self) -> int:
        '''ROI x position.'''
        return self._x

    @x.setter
    def x(self, x: int) -> None:
        self._x = int(x)

    @property
    def y(self) -> int:
        '''ROI y position.'''
        return self._y

    @y.setter
    def y(self, y: int) -> None:
        self._y = int(y)

    @property
    def w(self) -> int:
        '''ROI width.'''
        return self._w

    @w.setter
    def w(self, w: int) -> None:
        self._w = int(w)

    @property
    def h(self) -> int:
        '''ROI height.'''
        return self._h

    @h.setter
    def h(self, h: int) -> None:
        self._h = int(h)


class QROIFilter(QVideoFilter):

    display_name = 'Region of Interest'
    display_category = 'Preprocessing'

    '''Qt widget wrapper for :class:`ROIFilter`.'''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent, 'Region of Interest', ROIFilter())

    def _setupUi(self) -> None:
        super()._setupUi()
        self._xSpinbox = SpinBox(self, prefix='x: ',
                                 bounds=(0, None),
                                 value=self.filter.x, int=True)
        self._ySpinbox = SpinBox(self, prefix='y: ',
                                 bounds=(0, None),
                                 value=self.filter.y, int=True)
        self._wSpinbox = SpinBox(self, prefix='w: ',
                                 bounds=(1, None),
                                 step=8,
                                 value=self.filter.w, int=True)
        self._hSpinbox = SpinBox(self, prefix='h: ',
                                 bounds=(1, None),
                                 step=8,
                                 value=self.filter.h, int=True)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(2)
        grid.addWidget(self._xSpinbox, 0, 0)
        grid.addWidget(self._ySpinbox, 0, 1)
        grid.addWidget(self._wSpinbox, 1, 0)
        grid.addWidget(self._hSpinbox, 1, 1)
        self._layout.addLayout(grid)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        self._xSpinbox.valueChanged.connect(self.setX)
        self._ySpinbox.valueChanged.connect(self.setY)
        self._wSpinbox.valueChanged.connect(self.setW)
        self._hSpinbox.valueChanged.connect(self.setH)

    @QtCore.Slot(object)
    def setX(self, x: int) -> None:
        '''Set the ROI x position.'''
        self.filter.x = x
        self._xSpinbox.setValue(self.filter.x)

    @QtCore.Slot(object)
    def setY(self, y: int) -> None:
        '''Set the ROI y position.'''
        self.filter.y = y
        self._ySpinbox.setValue(self.filter.y)

    @QtCore.Slot(object)
    def setW(self, w: int) -> None:
        '''Set the ROI width.'''
        self.filter.w = w
        self._wSpinbox.setValue(self.filter.w)

    @QtCore.Slot(object)
    def setH(self, h: int) -> None:
        '''Set the ROI height.'''
        self.filter.h = h
        self._hSpinbox.setValue(self.filter.h)


if __name__ == '__main__':  # pragma: no cover
    QROIFilter.example()
