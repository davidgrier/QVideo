from QVideo.dvr.QAVIReader import QAVIReader
from QVideo.lib import QVideoSource


class QAVISource(QVideoSource):

    def __init__(self, reader: str | QAVIReader) -> None:
        if isinstance(reader, str):
            reader = QAVIReader(reader)
        super().__init__(reader)


def example() -> None:
    filename = QAVIReader.examplevideo()
    source = QAVISource(filename).start()
    print(filename)
    print(f'Running: {source._running}')
    print('done')
    source.stop()
    source.quit()
    source.wait()


if __name__ == '__main__':
    example()
