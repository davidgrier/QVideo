from .QOpenCVWriter import QOpenCVWriter


__all__ = ['QAVIWriter']


class QAVIWriter(QOpenCVWriter):

    '''Video writer for AVI files.

    Writes lossless video to an AVI container.  ``FFV1`` (Free Lossless
    Video Codec) is tried first for its superior compression and
    multithreaded encoding; ``HFYU`` (HuffYUV) is the fallback.

    See :class:`QOpenCVWriter` for full parameter and attribute
    documentation.
    '''

    CODECS = ('FFV1', 'HFYU')
