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
