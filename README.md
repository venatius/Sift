# Sift
Privacy-first local AI media organization

## Development setup

The current development environment is verified on Python 3.13.3 for Windows.
Create and activate a virtual environment,
then install the pinned Python dependencies with `python -m pip install -r requirements.txt`.
Run the synthetic fixture suite with `python -m unittest discover -s tests -v`.

Video metadata requires the external `ffprobe` executable on `PATH`; it is part
of FFmpeg and is not installed by the Python requirements. One Windows option
is `winget install --id Gyan.FFmpeg --exact`. The Gyan.dev full builds are
GPLv3-licensed; review the [build details](https://www.gyan.dev/ffmpeg/builds/)
and [FFmpeg license information](https://ffmpeg.org/legal.html). Sift does not
download or bundle FFmpeg. The current development environment uses
`ffprobe 9.0.2-full_build-www.gyan.dev`.

The app stores its SQLite library under `%LOCALAPPDATA%\Sift\sift.db`. Scanning
and media analysis are local and read-only. Set `LOCALAPPDATA` to a temporary
directory when running isolated tests.
