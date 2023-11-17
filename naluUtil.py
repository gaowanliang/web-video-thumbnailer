import struct


def SEINaluKeyframeSeparate(data):
    """
    判断是不是SEI开头的关键帧，一般来说这种关键帧是SEI+P帧的组合
    """

    # 判断是不是SEI开头的关键帧，即第一个字节是0x06
    if data[4] == 0x06:
        print("是带有SEI的关键帧")
        # 取出前4个字节，表示SEI帧的长度
        seiEndIndex = struct.unpack(">I", data[0:4])[0]
        data = data[4:]
        # 将其分离成两部分
        seiData = b"\x00\x00\x00\x00" + data[:seiEndIndex]  # 补上随意的4个字节，使其匹配正常的删除流程
        nalData = data[seiEndIndex:]
        # 去掉nalData的前4个表示长度的字节，并添加0x00 00 01，使其成为标准的NALU
        nalData = b"\x00\x00\x01" + nalData[4:]
        return seiData + nalData, seiData

    else:
        return data, b""


def sliceType(data):
    """
    判断是I帧还是P帧
    """
    # 对5取余
    sliceType = data % 5
    if sliceType == 0:
        return "P"
    elif sliceType == 1:
        return "B"
    elif sliceType == 2:
        return "I"
    elif sliceType == 3:
        return "SP"
    elif sliceType == 4:
        return "SI"
    else:
        return "Error"


# 判断是不是一个sample有多个nalu的情况，如果是，将其分离
def sampleNaluSeparate(data, size):
    """
    判断是不是一个sample有多个nalu的情况，如果是，将其分离
    """
    # 取出前4个字节，判断大小是不是和size相等
    if struct.unpack(">I", data[0:4])[0] == size:
        print("只有一个nalu")
        return data
    else:
        nalus = []
        print("有多个nalu")
        # 取出前4个字节，表示SEI帧的长度
        while len(data) > 0:
            naluSize = struct.unpack(">I", data[0:4])[0]
            data = data[4:]
            nalus.append(data[:naluSize])
            data = data[naluSize:]
        data = b""
        for nalu in nalus:
            data += b"\x00\x00\x01" + nalu
        return b"\x00\x00\x00\x00" + data  # 补上随意的4个字节，使其匹配正常的删除流程
