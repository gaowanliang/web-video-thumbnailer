# Web Video Thumbnailer
For a web video that can be downloaded in segments, it is possible to create an overview of the video by downloading only a small amount of binary data.

# requirements
- Python 3.6+
- ffmpeg

# Note
This is a very simple script that I wrote for my own use. It is not a complete program. If you want to use it, you need to modify the code yourself.

Currently, only H264 encoded MP4 files are supported, and due to the complexity of the MP4 file format, the code is not very robust, many MP4 files may not be supported at present.

# Usage
First, you need to **modify the web video url** in `main.py` and run the script. The script will generate a thumbnail image.

