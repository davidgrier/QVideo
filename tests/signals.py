'''Collect the emissions of a Qt signal in a list.

PyQt's ``QtTest.QSignalSpy`` is a sequence; PySide6's is not.  A list of
argument tuples behaves the same under every binding.
'''


def record(signal) -> list[tuple]:
    '''Return a list that receives the arguments of each emission.

    Parameters
    ----------
    signal : SignalInstance
        The signal to watch.

    Returns
    -------
    list[tuple]
        One tuple of arguments for each emission of *signal*, in order.
    '''
    received = []
    signal.connect(lambda *args: received.append(args))
    return received
