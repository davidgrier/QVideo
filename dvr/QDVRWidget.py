# -*- coding: utf-8 -*-

from PyQt5 import uic
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, pyqtProperty,
                          QObject, QThread)
from PyQt5.QtWidgets import (QFrame, QFileDialog)
import os
from typing import Optional

from QVideo.lib import (clickable, QVideoCamera)
from .QVideoWriter import QVideoWriter
from .QHDF5Writer import QHDF5Writer
from .QVideoPlayer import QVideoPlayer
from .QHDF5Player import QHDF5Player
from .icons_rc import *


import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QDVRWidget(QFrame):
    '''GUI for a Digital Video Recorder (DVR)

    Inherits
    --------
    PyQt5.QtWidgets.QFrame

    Properties
    ----------
    source: QVideoCamera
        Source of video frames to present and record

    filename: str
        Name of video file to save and record

    Methods
    -------
    All methods are invoked by widgets described in
    QDVRWidget.ui
    '''

    recording = pyqtSignal(bool)
    playing = pyqtSignal(bool)

    def __init__(self,
                 *args,
                 source: Optional[QVideoCamera] = None,
                 filename: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        dir = os.path.dirname(os.path.abspath(__file__))
        uipath = os.path.join(dir, 'QDVRWidget.ui')
        uic.loadUi(uipath, self)

        self._writer = None
        self._player = None
        self._framenumber = 0

        self.connectSignals()

        self.source = source
        self.filename = filename

    def connectSignals(self) -> None:
        '''Connects signals to slots for user interaction'''
        clickable(self.playEdit).connect(self.getPlayFilename)
        clickable(self.saveEdit).connect(self.getSaveFilename)
        self.recordButton.clicked.connect(self.record)
        self.stopButton.clicked.connect(self.stop)
        self.rewindButton.clicked.connect(self.rewind)
        self.pauseButton.clicked.connect(self.pause)
        self.playButton.clicked.connect(self.play)

    def is_recording(self) -> bool:
        '''Returns True if recording in progress'''
        return (self._writer is not None)

    def is_playing(self) -> bool:
        '''Returns True is video is playing'''
        return (self._player is not None)

    @pyqtSlot()
    def getPlayFilename(self) -> str:
        '''Returns file name of video to be played'''
        if self.is_recording():
            return ''
        get = QFileDialog.getOpenFileName
        filename, _ = get(self, 'Video File Name', self.filename,
                          'Video files (*.avi);;HDF5 files (*.h5)')
        if filename:
            self.playname = str(filename)
        return filename

    @pyqtSlot()
    def getSaveFilename(self) -> str:
        '''Returns files name of video to be recorded'''
        if self.is_recording():
            return
        get = QFileDialog.getSaveFileName
        filename, _ = get(self, 'Video File Name', self.filename,
                          'Video files (*.avi);;HDF5 files (*.h5)')
        if filename:
            self.filename = str(filename)
            self.playname = str(filename)
        return filename

    @pyqtSlot()
    def record(self) -> None:
        '''Implements functionality of Record button'''
        if self.is_playing():
            return
        if self.is_recording():
            self.stop()
            return
        if (self.filename == '') and (self.getSaveFilename() == ''):
            return
        logger.debug(f'Starting Recording: {self.filename}')
        extension = os.path.splitext(self.filename)[1]
        if extension == '.avi':
            self._writer = QVideoWriter(self.filename,
                                        self.source.shape,
                                        self.source.color,
                                        fps=self.source.fps,
                                        nframes=self.nframes.value(),
                                        nskip=self.nskip.value())
        elif extension == '.h5':
            self._writer = QHDF5Writer(self.filename,
                                       nframes=self.nframes.value(),
                                       nskip=self.nskip.value())
        else:
            logger.debug(f'unsupported file extension {extension}')
            return
        self._writer.frameNumber.connect(self.setFrameNumber)
        self._writer.finished.connect(self.stop)
        self._thread = QThread()
        self._thread.finished.connect(self._writer.close)
        self.source.newFrame.connect(self._writer.write)
        self._writer.moveToThread(self._thread)
        self._thread.start()
        self.recording.emit(True)

    @pyqtSlot()
    def play(self) -> None:
        '''Implements functionality of Play buttoon'''
        if self.is_recording():
            return
        if self.is_playing():
            self._player.pause(False)
            return
        if (self.playname == '') and (self.getPlayFilename() == ''):
            return
        self.framenumber = 0
        logger.debug(f'Starting Playback: {self.playname}')
        extension = os.path.splitext(self.playname)[1]
        if extension == '.avi':
            self._player = QVideoPlayer(self.playname)
        elif extension == '.h5':
            self._player = QHDF5Player(self.playname)
        else:
            logger.debug(f'unsupported file extension {extension}')
            return
        if self._player.isOpened():
            self.newFrame = self._player.newFrame
            self.newFrame.connect(self.stepFrameNumber)
            self._player.start()
            self.playing.emit(True)
        else:
            self._player = None

    @pyqtSlot()
    def pause(self) -> None:
        '''Implements functionality of Pause button'''
        if self.is_playing():
            state = self._player.isPaused()
            self._player.pause(not state)

    @pyqtSlot()
    def rewind(self) -> None:
        '''Implements functionality of Rewind button'''
        if self.is_playing():
            self._player.rewind()
            self.framenumber = 0

    @pyqtSlot()
    def stop(self) -> None:
        '''Implements functionality of Stop button'''
        if self.is_recording():
            logger.debug('Stopping Recording')
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._writer = None
            self.recording.emit(False)
        if self.is_playing():
            logger.debug('Stopping Playback')
            self.newFrame.disconnect()
            self._player.stop()
            self._player = None
            self.playing.emit(False)
        self.framenumber = 0

    @pyqtSlot(int)
    def setFrameNumber(self, framenumber: int) -> None:
        '''Sets frame number'''
        self.framenumber = framenumber

    @pyqtSlot()
    def stepFrameNumber(self) -> None:
        '''Increments frame number'''
        self.framenumber += 1

    @pyqtProperty(QObject)
    def source(self):
        return self._source

    @source.setter
    def source(self, source):
        self._source = source
        self.recordButton.setDisabled(source is None)

    @pyqtProperty(str)
    def filename(self) -> str:
        '''Returns file name from Save widget'''
        return str(self.saveEdit.text())

    @filename.setter
    def filename(self, filename: str) -> None:
        '''Sets file name in Save widget'''
        if filename is None:
            return
        if not (self.is_recording() or self.is_playing()):
            self.saveEdit.setText(os.path.expanduser(filename))
            self.playname = self.filename

    @pyqtProperty(str)
    def playname(self) -> str:
        '''Returns current filename from Play widget'''
        return str(self.playEdit.text())

    @playname.setter
    def playname(self, filename: str) -> None:
        '''Sets filename for Play widget'''
        if not (self.is_playing()):
            self.playEdit.setText(os.path.expanduser(filename))

    @pyqtProperty(int)
    def framenumber(self) -> int:
        '''Returns current frame number'''
        return self._framenumber

    @framenumber.setter
    def framenumber(self, number: int) -> None:
        '''Sets frame number'''
        self._framenumber = number
        self.frameNumber.display(self._framenumber)
