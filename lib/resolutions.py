import subprocess


def resolutions():
    # cmd = ['ffprobe', '-f', 'avfoundation', '-show_streams', '0']
    # cmd = 'ffprobe -f avfoundation -framerate 30 -i default -show_streams'.split()
    # cmd = 'ffmpeg -f avfoundation -list_formats 1 -i default'.split()
    cmd = 'ffmpeg -f avfoundation -list_devices true -i ""'.split()
    print(cmd)
    opts = dict(capture_output=True, text=True)
    return subprocess.run(cmd, **opts)


if __name__ == '__main__':
    print(resolutions().stderr)
    print(resolutions().stdout)
