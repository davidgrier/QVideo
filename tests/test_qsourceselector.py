'''Unit tests for dvr.QSourceSelector.'''
import unittest
from qtpy import QtCore, QtWidgets
from QVideo.dvr import QSourceSelector
from QVideo.tests.signals import record


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_selector(*names, **kwargs):
    selector = QSourceSelector(**kwargs)
    sources = {name: QtCore.QObject() for name in names}
    for name, source in sources.items():
        selector.addSource(name, source)
    return selector, sources


class TestSelection(unittest.TestCase):

    def test_there_is_no_source_before_one_is_added(self):
        selector = QSourceSelector()
        self.assertIsNone(selector.source)
        self.assertIsNone(selector.sourceName)

    def test_the_first_source_is_selected(self):
        selector, sources = make_selector('Raw', 'Filtered')
        self.assertIs(selector.source, sources['Raw'])
        self.assertEqual(selector.sourceName, 'Raw')

    def test_adding_a_source_does_not_announce_a_choice(self):
        selector = QSourceSelector()
        changes = record(selector.sourceChanged)
        selector.addSource('Raw', QtCore.QObject())
        self.assertEqual(changes, [])

    def test_choosing_a_name_selects_its_source(self):
        selector, sources = make_selector('Raw', 'Filtered')
        selector.sourceName = 'Filtered'
        self.assertIs(selector.source, sources['Filtered'])

    def test_clicking_a_button_selects_its_source(self):
        selector, sources = make_selector('Raw', 'Filtered')
        button = [b for b in selector._sources if b.text() == 'Filtered'][0]
        button.click()
        self.assertIs(selector.source, sources['Filtered'])

    def test_an_unknown_name_is_an_error(self):
        selector, _ = make_selector('Raw')
        with self.assertRaises(ValueError):
            selector.sourceName = 'Missing'

    def test_only_one_button_is_checked(self):
        selector, _ = make_selector('Raw', 'Filtered', 'Display')
        selector.sourceName = 'Display'
        checked = [b for b in selector._sources if b.isChecked()]
        self.assertEqual([b.text() for b in checked], ['Display'])


class TestSignal(unittest.TestCase):

    def test_a_choice_emits_the_source_once(self):
        selector, sources = make_selector('Raw', 'Filtered')
        changes = record(selector.sourceChanged)
        selector.sourceName = 'Filtered'
        self.assertEqual(changes, [(sources['Filtered'],)])

    def test_choosing_the_current_source_emits_nothing(self):
        selector, _ = make_selector('Raw', 'Filtered')
        changes = record(selector.sourceChanged)
        selector.sourceName = 'Raw'
        self.assertEqual(changes, [])

    def test_two_names_may_share_a_source(self):
        screen = QtCore.QObject()
        selector = QSourceSelector()
        selector.addSource('Display', screen)
        selector.addSource('Composite', screen)
        changes = record(selector.sourceChanged)
        selector.sourceName = 'Composite'
        self.assertEqual(changes, [(screen,)])
        self.assertEqual(selector.sourceName, 'Composite')


class TestLayout(unittest.TestCase):

    def test_buttons_fill_rows_of_the_given_width(self):
        selector, _ = make_selector('a', 'b', 'c', 'd', columns=3)
        grid = selector.layout()
        positions = [grid.getItemPosition(i)[:2]
                     for i in range(grid.count())]
        self.assertEqual(positions, [(0, 0), (0, 1), (0, 2), (1, 0)])

    def test_the_box_has_a_title(self):
        self.assertEqual(QSourceSelector().title(), 'Record from')
        self.assertEqual(QSourceSelector('Show').title(), 'Show')

    def test_disabling_the_box_disables_the_buttons(self):
        selector, _ = make_selector('Raw', 'Filtered')
        selector.setDisabled(True)
        self.assertFalse(any(b.isEnabled() for b in selector._sources))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
