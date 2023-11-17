# Copy as Python - from 010 Editor - byte count: 29 (0x1D)
buffer = b''.join([
    b'\x00\x00\x01\x67\x64\x00\x1F\xAC\xD9\x40\x50\x05\xBA\x6A\x0C\x02\x0C',
    b'\x80\x00\x00\x03\x00\x80\x00\x00\x19\x07\x8C\x18\xCB\x00'])

# Copy as Python - from 010 Editor - byte count: 9 (0x9)
buffer += b'\x00\x00\x01\x68\xEB\xE3\xCB\x22\xC0'

with open("demo1.h264", "wb") as f:
    f.write(buffer)

import subprocess

# 使用 FFmpeg 将 H264 数据解码为 jpg 数据
subprocess.run(["ffmpeg", "-y", "-i", "demo1.h264", f"temp-%03d.jpg"])
