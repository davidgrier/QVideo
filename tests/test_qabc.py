'''Unit tests for QABCMeta.'''
import unittest
from abc import ABCMeta, abstractmethod
import qtpy
from qtpy import QtCore, QtWidgets
from QVideo.lib._qabc import QABCMeta
from QVideo.lib.QCamera import QCamera
from QVideo.lib.QVideoReader import QVideoReader
from QVideo.lib.QVideoWriter import QVideoWriter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _Base(QtCore.QObject, metaclass=QABCMeta):
    changed = QtCore.Signal(int)

    @abstractmethod
    def read(self) -> int:
        pass


class _Concrete(_Base):
    def read(self) -> int:
        return 1


class TestQABCMeta(unittest.TestCase):

    def test_derives_from_both_metaclasses(self):
        self.assertTrue(issubclass(QABCMeta, ABCMeta))
        self.assertTrue(issubclass(QABCMeta, type(QtCore.QObject)))

    def test_abcmeta_comes_first(self):
        mro = QABCMeta.__mro__
        self.assertLess(mro.index(ABCMeta),
                        mro.index(type(QtCore.QObject)))

    def test_isinstance_works(self):
        self.assertIsInstance(_Concrete(), _Base)

    def test_signals_work(self):
        obj = _Concrete()
        received = []
        obj.changed.connect(received.append)
        obj.changed.emit(3)
        self.assertEqual(received, [3])

    @unittest.skipIf(qtpy.PYSIDE6, 'Shiboken does not enforce ABCs')
    def test_abstract_class_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            _Base()

    def test_framework_base_classes_use_it(self):
        for cls in (QCamera, QVideoReader, QVideoWriter):
            self.assertIs(type(cls), QABCMeta, cls.__name__)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
