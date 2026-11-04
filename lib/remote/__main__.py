'''Run the worker: ``python -m QVideo.lib.remote KEY ID RPCFD FRAMEFD``.'''
import sys

from QVideo.lib.remote.worker import main


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
