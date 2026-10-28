'''Unit tests for the splash screen of the applications.'''
import unittest
from qtpy import QtWidgets
from QVideo.lib._splash import say, splash


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestSplash(unittest.TestCase):

    def test_it_is_a_splash_screen_of_the_size_on_the_screen(self):
        screen = splash('Title')
        self.addCleanup(screen.close)
        self.assertIsInstance(screen, QtWidgets.QSplashScreen)
        self.assertEqual((screen.width(), screen.height()), (480, 240))

    def test_it_is_drawn_at_twice_the_size_for_sharp_displays(self):
        screen = splash()
        self.addCleanup(screen.close)
        self.assertEqual(screen.pixmap().devicePixelRatio(), 2.)
        self.assertEqual(screen.pixmap().width(), 960)

    def test_say_shows_the_message(self):
        screen = splash('Title')
        self.addCleanup(screen.close)
        screen.show()
        say(screen, 'Opening the camera...')
        self.assertEqual(screen.message(), 'Opening the camera...')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
