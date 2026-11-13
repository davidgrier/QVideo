'''Unit tests for WriteQueue.'''
import logging
import threading
import time
import unittest

from QVideo.lib._writequeue import WriteQueue


class Gate:
    '''A work function that records its batches and waits for a signal.'''

    def __init__(self, hold=False):
        self.batches = []
        self.threads = []
        self.entered = threading.Event()
        self.release = threading.Event()
        if not hold:
            self.release.set()

    def __call__(self, batch):
        self.threads.append(threading.current_thread())
        self.batches.append(dict(batch))
        self.entered.set()
        self.release.wait(5)


class TestWriting(unittest.TestCase):

    def test_a_value_is_written_in_another_thread(self):
        gate = Gate()
        queue = WriteQueue(gate)
        queue.put('width', 320, 1)
        self.assertTrue(queue.wait(5))
        self.assertEqual(gate.batches, [{'width': (320, 1)}])
        self.assertIsNot(gate.threads[0], threading.current_thread())

    def test_the_latest_value_of_a_name_is_kept(self):
        gate = Gate(hold=True)
        queue = WriteQueue(gate)
        queue.put('width', 1, 1)
        gate.entered.wait(5)                  # the worker has the first one
        for n in range(2, 50):
            queue.put('width', n, n)          # all of these wait
        gate.release.set()
        self.assertTrue(queue.wait(5))
        self.assertEqual(gate.batches, [{'width': (1, 1)},
                                        {'width': (49, 49)}])

    def test_the_order_is_that_of_the_last_touch(self):
        gate = Gate(hold=True)
        queue = WriteQueue(gate)
        queue.put('first', 0, 1)
        gate.entered.wait(5)
        queue.put('a', 1, 1)
        queue.put('b', 2, 1)
        queue.put('a', 3, 2)                  # a again: after b now
        gate.release.set()
        queue.wait(5)
        self.assertEqual(list(gate.batches[1]), ['b', 'a'])
        self.assertEqual(gate.batches[1]['a'], (3, 2))

    def test_what_is_written_while_it_writes_goes_in_the_next_batch(self):
        gate = Gate(hold=True)
        queue = WriteQueue(gate)
        queue.put('a', 1, 1)
        gate.entered.wait(5)
        queue.put('b', 2, 1)
        self.assertFalse(queue.idle())
        gate.release.set()
        queue.wait(5)
        self.assertEqual(gate.batches, [{'a': (1, 1)}, {'b': (2, 1)}])

    def test_the_thread_ends_when_there_is_nothing_to_write(self):
        gate = Gate()
        queue = WriteQueue(gate)
        queue.put('a', 1)
        queue.wait(5)
        gate.threads[0].join(5)
        self.assertFalse(gate.threads[0].is_alive())

    def test_a_new_value_after_idle_starts_a_new_worker(self):
        gate = Gate()
        queue = WriteQueue(gate)
        queue.put('a', 1)
        queue.wait(5)
        queue.put('a', 2)
        queue.wait(5)
        self.assertEqual(len(gate.batches), 2)


class TestWaiting(unittest.TestCase):

    def test_an_empty_queue_is_idle(self):
        queue = WriteQueue(Gate())
        self.assertTrue(queue.idle())
        self.assertTrue(queue.wait(0.1))

    def test_it_is_not_idle_while_it_writes(self):
        gate = Gate(hold=True)
        queue = WriteQueue(gate)
        queue.put('a', 1)
        gate.entered.wait(5)
        self.assertFalse(queue.idle())
        self.assertFalse(queue.wait(0.05))        # the time runs out
        gate.release.set()
        self.assertTrue(queue.wait(5))
        self.assertTrue(queue.idle())


class TestFailure(unittest.TestCase):

    def test_a_write_that_fails_is_logged_and_the_queue_goes_on(self):
        calls = []

        def work(batch):
            calls.append(dict(batch))
            if len(calls) == 1:
                raise RuntimeError('the camera said no')

        queue = WriteQueue(work, 'Test writer')
        with self.assertLogs('QVideo.lib._writequeue', 'ERROR') as logs:
            queue.put('a', 1)
            queue.wait(5)
        self.assertIn('Test writer: a write failed', logs.output[0])
        queue.put('b', 2)
        queue.wait(5)
        self.assertEqual(len(calls), 2)


class TestClosing(unittest.TestCase):

    def test_close_drops_what_waits_and_finishes_what_is_written(self):
        gate = Gate(hold=True)
        queue = WriteQueue(gate)
        queue.put('a', 1, 1)
        gate.entered.wait(5)
        queue.put('b', 2, 1)                      # waits behind the first
        closer = threading.Thread(target=queue.close)
        closer.start()
        time.sleep(0.05)
        self.assertTrue(closer.is_alive())        # it waits for the write
        gate.release.set()
        closer.join(5)
        self.assertFalse(closer.is_alive())
        self.assertEqual(gate.batches, [{'a': (1, 1)}])

    def test_nothing_is_written_after_it_is_closed(self):
        gate = Gate()
        queue = WriteQueue(gate)
        queue.close()
        queue.put('a', 1)
        self.assertTrue(queue.idle())
        self.assertEqual(gate.batches, [])

    def test_it_may_be_closed_twice(self):
        queue = WriteQueue(Gate())
        queue.put('a', 1)
        queue.close()
        queue.close()

    def test_it_may_be_closed_from_the_worker(self):
        queue = WriteQueue(lambda batch: queue.close())
        queue.put('a', 1)
        self.assertTrue(queue.wait(5))


if __name__ == '__main__':  # pragma: no cover
    logging.basicConfig()
    unittest.main()
