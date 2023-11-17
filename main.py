import requests
import struct
import os
import subprocess
import merge
import naluUtil


# set proxy / 设置代理
proxy = {}

url = "http://127.0.0.1:16666/2.mp4"  # web video url / 网络视频地址


videoSeconds = 0
videoTimeScale = 0

videoWidth = 0
videoHeight = 0
videoPPS = b""
videoSPS = b""
stcoLength = 0
chunkOffsetRawData = b""
videoChunkOffset = []
videoSampleOfChunkInfo = []
stscLength = 0
stscRawData = b""
stszLength = 0
stszRawData = b""
videoSampleOfChunk = []
videoIFrameNumber = []

stssRawData = b""
stssLength = 0

sttsLength = 0
sttsRawData = b""
videoSampleDelta = []

cttsLength = 0
cttsRawData = b""
videoSampleOffset = []

stuckHeader = b""
h264Sign = b"\x00\x00\x01"
chunk_size = 1024  # each chunk size / 每次读取的字节数


def getHeightWidthAndSeconds(data):
    global videoSeconds, videoWidth, videoHeight, videoTimeScale

    if videoTimeScale != 0:
        return

    if data.find(b"mdhd") > 0:  # 如果数据块中包含mdhd字符串
        index = data.find(b"mdhd") + 4  # 找到mdhd数据块的起始位置，向后偏移4字节
        # 从第13位到第17位读取时基的值，用大端序转换为整数
        time_scale = struct.unpack(">I", data[index + 12 : index + 12 + 4])[0]
        videoTimeScale = time_scale
        # 从第17位到第21位读取时长的值，用大端序转换为整数
        duration = struct.unpack(">I", data[index + 12 + 4 : index + 12 + 4 + 4])[0]
        videoSeconds = duration / time_scale  # 计算视频的秒数
    if data.find(b"tkhd") > 0:  # 如果数据块中包含tkhd字符串
        index = data.find(b"tkhd") + 4  # 找到mdhd数据块的起始位置，向后偏移4字节
        # 从第76位到第80位读取视频长度的值，用大端序转换为小数
        temp = struct.unpack(">I", data[index + 76 : index + 76 + 4])[0]
        if temp > 0:
            videoWidth = temp / 65536  # 读取到的值除以65536，得到视频的宽度
            # 从第80位到第84位读取视频宽度的值，用大端序转换为整数
            videoHeight = struct.unpack(">I", data[index + 80 : index + 80 + 4])[0]
            videoHeight = videoHeight / 65536  # 读取到的值除以65536，得到视频的高度


def getSPSAndPPS(data):
    global videoPPS, videoSPS

    if data.find(b"avcC") > 0:  # 如果数据块中包含avcC字符串
        index = data.find(b"avcC") + 4  # 找到avcC数据块的起始位置，向后偏移4字节
        # 从第8位到第9位读取SPS的长度，用大端序转换为整数
        sps_size = struct.unpack(">H", data[index + 6 : index + 6 + 2])[0]
        # 从第6位到第6+2+sps_size位读取SPS的数据
        videoSPS = data[index + 6 + 2 : index + 6 + 2 + sps_size]

        # 从第8+sps_size位到第8+sps_size+1位读取PPS的长度，用大端序转换为整数
        pps_size = struct.unpack(
            ">H", data[index + 8 + sps_size + 1 : index + 8 + sps_size + 1 + 2]
        )[0]

        # 从第11+sps_size位到第11+sps_size+pps_size位读取PPS的数据
        videoPPS = data[index + 9 + sps_size + 2 : index + 9 + sps_size + 2 + pps_size]

        # 伪造H264的头部数据
        buffer = b"\x00\x00\x01"
        videoSPS = buffer + videoSPS
        videoPPS = buffer + videoPPS


def getChunkOffset(data, stuckHeader):
    global stcoLength, chunkOffsetRawData, videoChunkOffset

    if len(chunkOffsetRawData) > 0 and len(chunkOffsetRawData) < stcoLength * 4:
        if stcoLength * 4 - len(chunkOffsetRawData) > len(data):
            chunkOffsetRawData += data
        else:
            chunkOffsetRawData += data[: stcoLength * 4 - len(chunkOffsetRawData)]
        return

    if len(chunkOffsetRawData) == stcoLength * 4 and stcoLength > 0:
        for i in range(stcoLength):
            videoChunkOffset.append(
                struct.unpack(">I", chunkOffsetRawData[i * 4 : i * 4 + 4])[0]
            )

        print(f"总chunk数：{len(videoChunkOffset)}")
        return

    if data.find(b"stco") > 0:  # 如果数据块中包含stco字符串
        index = data.find(b"stco") + 4  # 找到stco数据块的起始位置，向后偏移4字节
    if stuckHeader.find(b"stco") > 0:  # 如果数据块中包含stco字符串
        index = stuckHeader.find(
            b"stco"
        )  # 找到stco数据块的起始位置，向后偏移4字节，由于stuckHeader是后4个字节，所以不需要再偏移4字节
        # 从第8位到第12位读取stco的长度，用大端序转换为整数
    stcoLength = struct.unpack(">I", data[index + 4 : index + 4 + 4])[0]
    print(stcoLength)

    # 从第8位开始，将chunk offset数据块的数据读取出来，每个chunk offset数据块4个字节，直到读取完毕
    temp = data[index + 8 :]
    if len(temp) > stcoLength * 4:
        chunkOffsetRawData += temp[: stcoLength * 4]
    else:
        chunkOffsetRawData += temp


def getSampleOfChunkInfo(data, stuckHeader):
    global stscLength, stscRawData, videoSampleOfChunkInfo
    if len(stscRawData) > 0 and len(stscRawData) < stscLength * 12:
        if stscLength * 12 - len(stscRawData) > len(data):
            stscRawData += data
        else:
            stscRawData += data[: stscLength * 12 - len(stscRawData)]
        return

    if len(stscRawData) == stscLength * 12 and stscLength > 0:
        for i in range(stscLength):
            videoSampleOfChunkInfo.append(
                {
                    "first_chunk": struct.unpack(
                        ">I", stscRawData[i * 12 : i * 12 + 4]
                    )[0],
                    "samples_per_chunk": struct.unpack(
                        ">I", stscRawData[i * 12 + 4 : i * 12 + 8]
                    )[0],
                    "sample_description_index": struct.unpack(
                        ">I", stscRawData[i * 12 + 8 : i * 12 + 12]
                    )[0],
                }
            )

        return

    if data.find(b"stsc") > 0:  # 如果数据块中包含stsc字符串
        index = data.find(b"stsc") + 4  # 找到stsc数据块的起始位置，向后偏移4字节
    if stuckHeader.find(b"stsc") > 0:  # 如果数据块中包含stsc字符串
        index = stuckHeader.find(
            b"stsc"
        )  # 找到stsc数据块的起始位置，向后偏移4字节，由于stuckHeader是后4个字节，所以不需要再偏移4字节
        # 取出stsc数据块的数据数量
    print(data)
    print(data[index + 4 : index + 4 + 4])
    stscLength = struct.unpack(">I", data[index + 4 : index + 4 + 4])[0]
    if len(data[index + 8 :]) > stscLength * 12:
        for i in range(stscLength):
            videoSampleOfChunkInfo.append(
                {
                    "first_chunk": struct.unpack(
                        ">I", data[index + 8 + i * 12 : index + 8 + i * 12 + 4]
                    )[0],
                    "samples_per_chunk": struct.unpack(
                        ">I", data[index + 8 + i * 12 + 4 : index + 8 + i * 12 + 8]
                    )[0],
                    "sample_description_index": struct.unpack(
                        ">I", data[index + 8 + i * 12 + 8 : index + 8 + i * 12 + 12]
                    )[0],
                }
            )
    else:
        stscRawData += data[index + 8 :]


def getSampleOfChunk(data, stuckHeader):
    global stszLength, stszRawData, videoSampleOfChunk
    if len(stszRawData) > 0 and len(stszRawData) < stszLength * 4:
        if stszLength * 4 - len(stszRawData) > len(data):
            stszRawData += data
        else:
            stszRawData += data[: stszLength * 4 - len(stszRawData)]
        return

    if (
        len(stszRawData) == stszLength * 4
        and stszLength > 0
        and len(videoSampleOfChunk) == 0
    ):
        for i in range(stszLength):
            videoSampleOfChunk.append(
                struct.unpack(">I", stszRawData[i * 4 : i * 4 + 4])[0]
            )

        print(videoSampleOfChunk[-1])
        return

    if data.find(b"stsz") > 0:  # 如果数据块中包含stsz字符串
        index = data.find(b"stsz") + 4  # 找到stsz数据块的起始位置，向后偏移4字节
    if stuckHeader.find(b"stsz") > 0:  # 如果数据块中包含stsz字符串
        index = stuckHeader.find(
            b"stsz"
        )  # 找到stsz数据块的起始位置，向后偏移4字节，由于stuckHeader是后4个字节，所以不需要再偏移4字节
        # 取出stsz数据块的数据数量
    stszLength = struct.unpack(">I", data[index + 8 : index + 8 + 4])[0]
    if len(data[index + 12 :]) > stszLength * 4:
        for i in range(stszLength):
            videoSampleOfChunk.append(
                struct.unpack(">I", data[index + 12 + i * 4 : index + 12 + i * 4 + 4])[
                    0
                ]
            )
    else:
        stszRawData += data[index + 12 :]


def getIFrameNumber(data, stuckHeader):
    global stssLength, stssRawData, videoIFrameNumber
    if len(stssRawData) > 0 and len(stssRawData) < stssLength * 4:
        if stssLength * 4 - len(stssRawData) > len(data):
            stssRawData += data
        else:
            stssRawData += data[: stssLength * 4 - len(stssRawData)]
        return

    if (
        len(stssRawData) == stssLength * 4
        and stssLength > 0
        and len(videoIFrameNumber) == 0
    ):
        for i in range(stssLength):
            videoIFrameNumber.append(
                struct.unpack(">I", stssRawData[i * 4 : i * 4 + 4])[0]
            )

        print(f"最后一位IFrame:{videoIFrameNumber[-1]}")
        return

    if data.find(b"stss") > 0:  # 如果数据块中包含stsz字符串
        index = data.find(b"stss") + 4  # 找到stsz数据块的起始位置，向后偏移4字节
    if stuckHeader.find(b"stss") > 0:  # 如果数据块中包含stsz字符串
        index = stuckHeader.find(
            b"stss"
        )  # 找到stsz数据块的起始位置，向后偏移4字节，由于stuckHeader是后4个字节，所以不需要再偏移4字节
        # 取出stsz数据块的数据数量
    stssLength = struct.unpack(">I", data[index + 4 : index + 4 + 4])[0]
    if len(data[index + 8 :]) > stssLength * 4:
        for i in range(stssLength):
            videoIFrameNumber.append(
                struct.unpack(">I", data[index + 8 + i * 4 : index + 8 + i * 4 + 4])[0]
            )
    else:
        stssRawData += data[index + 8 :]


def getSampleDelta(data, stuckHeader):
    global videoSampleDelta, sttsLength, sttsRawData
    if len(sttsRawData) > 0 and len(sttsRawData) < sttsLength * 8:
        if sttsLength * 8 - len(sttsRawData) > len(data):
            sttsRawData += data
        else:
            sttsRawData += data[: sttsLength * 8 - len(sttsRawData)]
        return

    if (
        len(sttsRawData) == sttsLength * 8
        and sttsLength > 0
        and len(videoSampleDelta) == 0
    ):
        for i in range(sttsLength):
            videoSampleDelta.append(
                {
                    "sample_count": struct.unpack(">I", sttsRawData[i * 8 : i * 8 + 4])[
                        0
                    ],
                    "sample_delta": struct.unpack(
                        ">I", sttsRawData[i * 8 + 4 : i * 8 + 8]
                    )[0],
                }
            )

        print(videoSampleDelta[-1])
        return

    if data.find(b"stts") > 0:  # 如果数据块中包含stts字符串
        index = data.find(b"stts") + 4  # 找到stts数据块的起始位置，向后偏移4字节
    if stuckHeader.find(b"stts") > 0:  # 如果数据块中包含stts字符串
        index = stuckHeader.find(
            b"stts"
        )  # 找到stts数据块的起始位置，向后偏移4字节，由于stuckHeader是后4个字节，所以不需要再偏移4字节
        # 取出stts数据块的数据数量
    sttsLength = struct.unpack(">I", data[index + 4 : index + 4 + 4])[0]
    if len(data[index + 8 :]) > sttsLength * 8:
        for i in range(sttsLength):
            videoSampleDelta.append(
                {
                    "sample_count": struct.unpack(
                        ">I", data[index + 8 + i * 8 : index + 8 + i * 8 + 4]
                    )[0],
                    "sample_delta": struct.unpack(
                        ">I", data[index + 8 + i * 8 + 4 : index + 8 + i * 8 + 8]
                    )[0],
                }
            )
    else:
        sttsRawData += data[index + 8 :]


video_size = 0  # 视频的大小
r = requests.get(url, stream=True, proxies=proxy)  # 使用stream模式获取视频数据
for data in r.iter_content(chunk_size=chunk_size):  # 迭代获取每个数据块，每次chunk_size字节
    stuckHeader += data[:4]  # 读取前4个字节
    if stcoLength > 0 and len(videoChunkOffset) == 0:
        getChunkOffset(data, stuckHeader)
        # continue
    if stscLength > 0 and len(videoSampleOfChunkInfo) == 0:
        getSampleOfChunkInfo(data, stuckHeader)
        # continue
    if stszLength > 0 and len(videoSampleOfChunk) == 0:
        getSampleOfChunk(data, stuckHeader)
        # continue
    if stssLength > 0 and len(videoIFrameNumber) == 0:
        getIFrameNumber(data, stuckHeader)
        # continue
    if sttsLength > 0 and len(videoSampleDelta) == 0:
        getSampleDelta(data, stuckHeader)
        # continue
    if (
        len(videoChunkOffset) > 0
        and len(videoSampleOfChunkInfo) > 0
        and len(videoSampleOfChunk) > 0
        and len(videoIFrameNumber) > 0
        and len(videoSampleDelta) > 0
        and videoPPS != b""
        and videoSPS != b""
    ):
        break

    if (data.find(b"mdhd") > 0 or stuckHeader.find(b"mdhd") > 0) and videoHeight == 0:
        # 如果数据块中包含mdhd字符串
        getHeightWidthAndSeconds(data)  # 获取视频的宽度、高度和秒数
    if (data.find(b"avcC") > 0 or stuckHeader.find(b"avcC") > 0) and videoPPS == b"":
        getSPSAndPPS(data)  # 获取视频的SPS和PPS数据
    if (data.find(b"stco") > 0 or stuckHeader.find(b"stco") > 0) and len(
        videoChunkOffset
    ) == 0:
        getChunkOffset(data, stuckHeader)  # 获取视频的chunk offset数据
    if (data.find(b"stsc") > 0 or stuckHeader.find(b"stsc") > 0) and len(
        videoSampleOfChunkInfo
    ) == 0:
        getSampleOfChunkInfo(data, stuckHeader)  # 获取视频的sample of chunk数据
    if (data.find(b"stsz") > 0 or stuckHeader.find(b"stsz") > 0) and len(
        videoSampleOfChunk
    ) == 0:
        getSampleOfChunk(data, stuckHeader)  # 获取视频的sample of chunk数据
    if (data.find(b"stss") > 0 or stuckHeader.find(b"stss") > 0) and len(
        videoIFrameNumber
    ) == 0:
        getIFrameNumber(data, stuckHeader)  # 获取视频的I帧数据
    if (data.find(b"stts") > 0 or stuckHeader.find(b"stts") > 0) and len(
        videoSampleDelta
    ) == 0:
        getSampleDelta(data, stuckHeader)  # 获取视频的delta数据

    stuckHeader = data[-4:]

    if data.find(b"mdat") > 0:  # 如果数据块中包含mdat字符串
        index = data.find(b"mdat")  # 找到mdat数据块的起始位置
        # 读取mdat前的4个字节，如果结果是b'\x00\x00\x00\x01'，则mdat数据块的大小需要用64位表示，需要读取mdat后面的8个字节
        if data[index - 4 : index] == b"\x00\x00\x00\x01":
            video_size = struct.unpack(">Q", data[index + 4 : index + 12])[0]
        else:  # 否则mdat数据块的大小用32位表示，需要读取mdat前面的4个字节
            video_size = struct.unpack(">I", data[index - 4 : index])[0]
        break  # 跳出循环


video_data = b""  # 初始化视频数据为空字节串
alreadyRead = 0  # 已经读取的字节数
# 如果视频数据的大小大于0，则使用Range请求头跳过数据部分，去查moov数据块
if video_size > 0:
    print(f"视频大小：{round(video_size/(1024*1024),2)}MB, 字节数{video_size}")  # 打印视频的大小
    print(f"跳过{video_size}字节数据，去查moov数据块")
    headers = {"Range": f"bytes={video_size}-"}
    r = requests.get(url, headers=headers, stream=True, proxies=proxy)
    alreadyRead = video_size  # 已经读取的字节数

    for data in r.iter_content(chunk_size=chunk_size):  # 迭代获取每个数据块，每次chunk_size字节
        alreadyRead += len(data)  # 已经读取的字节数加上本次读取的字节数
        # print(f"已经读取{round(alreadyRead/(1024*1024),2)}MB, 字节数{alreadyRead}")
        stuckHeader += data[:4]  # 读取前4个字节
        if stcoLength > 0 and len(videoChunkOffset) == 0:
            getChunkOffset(data, stuckHeader)
            stuckHeader = data[-4:]  # 读取后4个字节
            # continue
        if stscLength > 0 and len(videoSampleOfChunkInfo) == 0:
            getSampleOfChunkInfo(data, stuckHeader)
            stuckHeader = data[-4:]
            # continue
        if stszLength > 0 and len(videoSampleOfChunk) == 0:
            getSampleOfChunk(data, stuckHeader)
            stuckHeader = data[-4:]
            # continue
        if stssLength > 0 and len(videoIFrameNumber) == 0:
            getIFrameNumber(data, stuckHeader)
            stuckHeader = data[-4:]
            # continue
        if sttsLength > 0 and len(videoSampleDelta) == 0:
            getSampleDelta(data, stuckHeader)
            stuckHeader = data[-4:]
            # continue
        if (
            len(videoChunkOffset) > 0
            and len(videoSampleOfChunkInfo) > 0
            and len(videoSampleOfChunk) > 0
            and len(videoIFrameNumber) > 0
            and len(videoSampleDelta) > 0
            and videoPPS != b""
            and videoSPS != b""
        ):
            break
        video_data += data
        if (
            data.find(b"mdhd") > 0 or stuckHeader.find(b"mdhd") > 0
        ) and videoHeight == 0:
            # 如果数据块中包含mdhd字符串
            getHeightWidthAndSeconds(data)  # 获取视频的宽度、高度和秒数
        if (
            data.find(b"avcC") > 0 or stuckHeader.find(b"avcC") > 0
        ) and videoPPS == b"":
            getSPSAndPPS(data)  # 获取视频的SPS和PPS数据
        if (data.find(b"stco") > 0 or stuckHeader.find(b"stco") > 0) and len(
            videoChunkOffset
        ) == 0:
            getChunkOffset(data, stuckHeader)  # 获取视频的chunk offset数据
        if (data.find(b"stsc") > 0 or stuckHeader.find(b"stsc") > 0) and len(
            videoSampleOfChunkInfo
        ) == 0:
            getSampleOfChunkInfo(data, stuckHeader)  # 获取视频的sample of chunk数据
        if (data.find(b"stsz") > 0 or stuckHeader.find(b"stsz") > 0) and len(
            videoSampleOfChunk
        ) == 0:
            getSampleOfChunk(data, stuckHeader)  # 获取视频的sample of chunk数据
        if (data.find(b"stss") > 0 or stuckHeader.find(b"stss") > 0) and len(
            videoIFrameNumber
        ) == 0:
            getIFrameNumber(data, stuckHeader)  # 获取视频的I帧数据
        if (data.find(b"stts") > 0 or stuckHeader.find(b"stts") > 0) and len(
            videoSampleDelta
        ) == 0:
            getSampleDelta(data, stuckHeader)  # 获取视频的delta数据

        stuckHeader = data[-4:]


# 根据stsc，重整sample of chunk数据
if len(videoSampleOfChunkInfo) > 1:
    tempStandardNum = 0
    formatChunkOffset = {}
    copySampleofChunk = videoSampleOfChunk.copy()
    tempSampleIndex = 0

    for i in range(len(videoChunkOffset)):
        if tempStandardNum == len(videoSampleOfChunkInfo) - 1:
            if i + 1 >= videoSampleOfChunkInfo[tempStandardNum]["first_chunk"]:
                ii = videoSampleOfChunkInfo[tempStandardNum]["samples_per_chunk"]
                if ii > 1:
                    iip = []
                    for j in range(ii):
                        iip.append(copySampleofChunk.pop(0))
                    for k in range(ii):
                        formatChunkOffset[tempSampleIndex] = {
                            "chunk_id": i,
                            "chunk_offset": videoChunkOffset[i],
                            "sample": iip,
                            "sampleIndex": k,
                        }
                        tempSampleIndex += 1

                else:
                    formatChunkOffset[tempSampleIndex] = {
                        "chunk_id": i,
                        "chunk_offset": videoChunkOffset[i],
                        "sample": copySampleofChunk.pop(0),
                        "sampleIndex": 0,
                    }
                    tempSampleIndex += 1
        else:
            if (
                i + 1 >= videoSampleOfChunkInfo[tempStandardNum]["first_chunk"]
                and i + 1 < videoSampleOfChunkInfo[tempStandardNum + 1]["first_chunk"]
            ):
                ii = videoSampleOfChunkInfo[tempStandardNum]["samples_per_chunk"]
                if ii > 1:
                    iip = []
                    for j in range(ii):
                        iip.append(copySampleofChunk.pop(0))
                    for k in range(ii):
                        formatChunkOffset[tempSampleIndex] = {
                            "chunk_id": i,
                            "chunk_offset": videoChunkOffset[i],
                            "sample": iip,
                            "sampleIndex": k,
                        }
                        tempSampleIndex += 1
                else:
                    formatChunkOffset[tempSampleIndex] = {
                        "chunk_id": i,
                        "chunk_offset": videoChunkOffset[i],
                        "sample": copySampleofChunk.pop(0),
                        "sampleIndex": 0,
                    }
                    tempSampleIndex += 1
            else:
                tempStandardNum += 1
                ii = videoSampleOfChunkInfo[tempStandardNum]["samples_per_chunk"]
                if ii > 1:
                    iip = []
                    for j in range(ii):
                        iip.append(copySampleofChunk.pop(0))
                    for k in range(ii):
                        formatChunkOffset[tempSampleIndex] = {
                            "chunk_id": i,
                            "chunk_offset": videoChunkOffset[i],
                            "sample": iip,
                            "sampleIndex": k,
                        }
                        tempSampleIndex += 1
                else:
                    formatChunkOffset[tempSampleIndex] = {
                        "chunk_id": i,
                        "chunk_offset": videoChunkOffset[i],
                        "sample": copySampleofChunk.pop(0),
                        "sampleIndex": 0,
                    }
                    tempSampleIndex += 1

    print(formatChunkOffset, len(formatChunkOffset))
    # print(f"实际Chunk offset数量：{len(videoChunkOffset)}, 计算后的数量：{tempSampleIndex}")

print(f"秒数：{videoSeconds}")  # 打印视频的秒数
# 换算为小时、分钟和秒
hours = int(videoSeconds / 3600)
minutes = int((videoSeconds - hours * 3600) / 60)
seconds = int(videoSeconds - hours * 3600 - minutes * 60)
print(f"{hours}:{minutes}:{seconds}")  # 打印视频的时长


print(f"视频宽度：{videoWidth}，视频高度：{videoHeight}")  # 打印视频的宽度和高度
# 打印SPS和PPS数据
print(f"SPS数据：{videoSPS}")
print(f"PPS数据：{videoPPS}")
print(f"stsc:{videoSampleOfChunkInfo}")
print(f"chunk offset:{len(videoChunkOffset)}")
print(f"sample:{len(videoSampleOfChunk)}")
print(f"I Frame:{videoIFrameNumber}")
# print(f"delta:{videoSampleDelta}")


secondList = []

if len(videoSampleOfChunkInfo) <= 1:
    # 找到中间的I帧
    middleIFrame = videoIFrameNumber[int(len(videoIFrameNumber) / 3)]
    print(f"中间的I帧：{middleIFrame}")
    # 获取这个I帧的偏移
    offset = videoChunkOffset[middleIFrame - 1]
    # 获取这个I帧的大小
    middleIFrameSize = videoSampleOfChunk[middleIFrame - 1]
    nextIFrame = videoIFrameNumber[int(len(videoIFrameNumber) / 3) + 1]
    # 获取下一个I帧的偏移
    nextOffset = videoChunkOffset[nextIFrame - 1]
    print(
        f"中间的I帧偏移：{offset}, 大小：{middleIFrameSize}，大小+偏移：{offset+middleIFrameSize}，下一个I帧偏移：{nextOffset-offset+middleIFrameSize}"
    )


for imageIndex in range(21):
    time = int(videoSeconds / 21 * imageIndex)
    secondList.append(time)
    if imageIndex == 0:
        continue
    # 换算成时间刻度
    timeScale = time * videoTimeScale
    # 换算成sample
    sampleNum = int(timeScale / videoSampleDelta[0]["sample_delta"])

    previousIFrame = 0
    # 找到距离最近的两个I帧，将其夹在中间
    for i in range(len(videoIFrameNumber)):
        if videoIFrameNumber[i] <= sampleNum:
            previousIFrame = videoIFrameNumber[i]

    print(f"计算出的最接近选中时间的帧序号{sampleNum}, 前一个I帧序号{previousIFrame}")

    # 从前后10帧中找到数据量最大的帧

    maxSampleNum = 0
    maxSampleSize = 0
    for i in range(sampleNum - 10, sampleNum + 10):
        if videoSampleOfChunk[i] > maxSampleSize:
            maxSampleSize = videoSampleOfChunk[i]
            maxSampleNum = i
    sampleNum = maxSampleNum

    print(maxSampleNum, maxSampleSize)

    # 根据实际取出的块，重算时间
    time = videoSampleDelta[0]["sample_delta"] * sampleNum / videoTimeScale
    secondList[imageIndex] = time

    if len(videoSampleOfChunkInfo) <= 1:
        headers = {"Range": f"bytes={videoChunkOffset[sampleNum-1]}-"}
        r = requests.get(url, headers=headers, stream=True, proxies=proxy)

        iFrameData = b""  # 初始化当前帧数据为空字节串

        for data in r.iter_content(chunk_size=chunk_size):  # 迭代获取每个数据块，每次chunk_size字节
            subByte = videoSampleOfChunk[sampleNum - 1] - len(iFrameData)
            if subByte > 0:
                if len(data) > subByte:
                    iFrameData += data[:subByte]
                else:
                    iFrameData += data
            else:
                break
        iFrameData = naluUtil.sampleNaluSeparate(
            iFrameData, videoSampleOfChunk[sampleNum - 1]
        )

        if sampleNum != previousIFrame:
            headers = {"Range": f"bytes={videoChunkOffset[previousIFrame-1]}-"}
            r = requests.get(url, headers=headers, stream=True, proxies=proxy)
            tempData = b""
            for data in r.iter_content(
                chunk_size=chunk_size
            ):  # 迭代获取每个数据块，每次chunk_size字节
                subByte = videoSampleOfChunk[previousIFrame - 1] - len(tempData)
                if subByte > 0:
                    if len(data) > subByte:
                        tempData += data[:subByte]
                    else:
                        tempData += data
                else:
                    break
            tempData = naluUtil.sampleNaluSeparate(
                tempData, videoSampleOfChunk[previousIFrame - 1]
            )
            iFrameData = tempData + h264Sign + iFrameData[4:]
    else:
        print(sampleNum, formatChunkOffset[sampleNum])
        print(f"选择的sampleNum大小：{videoSampleOfChunk[sampleNum]}")
        trueOffset = formatChunkOffset[sampleNum]["chunk_offset"]
        if formatChunkOffset[sampleNum]["sampleIndex"] > 0:
            for i in range(formatChunkOffset[sampleNum]["sampleIndex"]):
                trueOffset += formatChunkOffset[sampleNum]["sample"][i]

        headers = {"Range": f"bytes={trueOffset}-"}
        r = requests.get(url, headers=headers, stream=True, proxies=proxy)

        iFrameData = b""  # 初始化当前帧数据为空字节串

        for data in r.iter_content(chunk_size=chunk_size):  # 迭代获取每个数据块，每次chunk_size字节
            subByte = videoSampleOfChunk[sampleNum] - len(iFrameData)
            if subByte > 0:
                if len(data) > subByte:
                    iFrameData += data[:subByte]
                else:
                    iFrameData += data
            else:
                break
        iFrameData = naluUtil.sampleNaluSeparate(
            iFrameData, videoSampleOfChunk[sampleNum]
        )

        if sampleNum != previousIFrame:
            print(previousIFrame, formatChunkOffset[previousIFrame - 1])
            print(f"选择的previousIFrame大小：{videoSampleOfChunk[previousIFrame-1]}")
            trueOffset = formatChunkOffset[previousIFrame - 1]["chunk_offset"]
            if formatChunkOffset[previousIFrame - 1]["sampleIndex"] > 0:
                for i in range(formatChunkOffset[previousIFrame - 1]["sampleIndex"]):
                    trueOffset += formatChunkOffset[previousIFrame - 1]["sample"][i]
            headers = {"Range": f"bytes={trueOffset}-"}
            r = requests.get(url, headers=headers, stream=True, proxies=proxy)
            tempData = b""

            for data in r.iter_content(
                chunk_size=chunk_size
            ):  # 迭代获取每个数据块，每次chunk_size字节
                subByte = videoSampleOfChunk[previousIFrame - 1] - len(tempData)

                if subByte > 0:
                    if len(data) > subByte:
                        tempData += data[:subByte]
                    else:
                        tempData += data
                else:
                    break

            if iFrameData[4] == 0x06:
                tempData, seiData = naluUtil.SEINaluKeyframeSeparate(tempData)
            else:
                tempData = naluUtil.sampleNaluSeparate(
                    tempData, videoSampleOfChunk[previousIFrame - 1]
                )
            if iFrameData[4] == 0x41 and seiData != b"":
                iFrameData = (
                    tempData + h264Sign + seiData[4:] + h264Sign + iFrameData[4:]
                )
            else:
                iFrameData = tempData + h264Sign + iFrameData[4:]
        else:
            if iFrameData[4] == 0x06:
                iFrameData, _ = naluUtil.SEINaluKeyframeSeparate(iFrameData)

            iFrameData = h264Sign + iFrameData

    # 将I帧数据写入文件
    with open("demo.h264", "wb") as f:
        f.write(videoSPS + videoPPS + h264Sign + iFrameData[4:])
    # 使用 FFmpeg 将 H264 数据解码为 jpg 数据
    subprocess.run(["ffmpeg", "-y", "-i", "demo.h264", f"temp-{imageIndex}-%03d.jpg"])
    # exit(0)


# n位数不足补0
def addZero(n, num):
    if len(str(num)) < n:
        return "0" * (n - len(str(num))) + str(num)
    else:
        return str(num)


# 将秒转换为小时分钟秒，两位数不足补0
for i in range(len(secondList)):
    hours = int(secondList[i] / 3600)
    minutes = int((secondList[i] - hours * 3600) / 60)
    seconds = int(secondList[i] - hours * 3600 - minutes * 60)
    secondList[i] = f"{addZero(2,hours)}:{addZero(2,minutes)}:{addZero(2,seconds)}"

tempImageList = []
# 遍历当前文件夹下的所有文件，取出所有temp前缀，jpg后缀的文件
for file_name in os.listdir("."):
    if file_name.startswith("temp") and file_name.endswith(".jpg"):
        tempImageList.append(file_name)
imageList = []
printSecondList = []
for i in range(len(secondList)):
    # 找出所有temp-i 前缀的文件，取出尾号最大的文件
    maxNum = 0
    minNum = 999999
    for file_name in tempImageList:
        if file_name.startswith(f"temp-{i}-"):
            num = int(file_name.split("-")[-1].split(".")[0])
            if num > maxNum:
                maxNum = num
            if num < minNum:
                minNum = num
    if maxNum == 0:  # 如果没有找到temp-i-xxx.jpg文件，则跳过
        continue
    # 将尾号最大的文件名加入imageList

    imageList.append(f"temp-{i}-{addZero(3,maxNum)}.jpg")
    printSecondList.append(secondList[i])


merge.merge_images(imageList, printSecondList, 5)  # 合并图片


# 清除所有的临时图片
for file_name in os.listdir("."):
    if file_name.startswith("temp") and file_name.endswith(".jpg"):
        os.remove(file_name)
