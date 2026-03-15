from .QOpenCVWriter import QOpenCVWriter


__all__ = ['QMP4Writer']


class QMP4Writer(QOpenCVWriter):

    '''Video writer for MP4 files.

    Writes video to an MP4 container using lossy compression.
    ``avc1`` (H.264) is tried first for best compression and broad
    player compatibility; ``mp4v`` (MPEG-4 Part 2) is the fallback
    and is universally available in OpenCV builds.

    .. note::
        The MP4 container does not support lossless codecs such as
        FFV1 or HuffYUV.  Use :class:`QAVIWriter` when lossless
        recording is required.

    See :class:`QOpenCVWriter` for full parameter and attribute
    documentation.
    '''

    CODECS = ('avc1', 'mp4v')
