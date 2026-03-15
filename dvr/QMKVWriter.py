from .QOpenCVWriter import QOpenCVWriter


__all__ = ['QMKVWriter']


class QMKVWriter(QOpenCVWriter):

    '''Video writer for MKV (Matroska) files.

    Writes lossless video to an MKV container.  ``FFV1`` (Free Lossless
    Video Codec) is tried first; the MKV container is the standardized
    home for FFV1 v3 and offers better long-term compatibility than AVI
    for lossless archival.  ``HFYU`` (HuffYUV) is the fallback.

    See :class:`QOpenCVWriter` for full parameter and attribute
    documentation.
    '''

    CODECS = ('FFV1', 'HFYU')
