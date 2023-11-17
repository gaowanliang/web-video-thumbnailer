import base64

sps_parser_offset = 0


def sps_parser_read_bits(buffer, count):
    global sps_parser_offset
    result = 0
    index = sps_parser_offset // 8
    bit_number = sps_parser_offset - (index * 8)
    out_bit_number = count - 1
    for _ in range(count):
        if buffer[index] << bit_number & 0x80:
            result |= 1 << out_bit_number
        if (bit_number := bit_number + 1) > 7:
            bit_number = 0
            index += 1
        out_bit_number -= 1
    sps_parser_offset += count
    return result


def sps_parser_read_ueg(buffer):
    global sps_parser_offset
    bitcount = 0

    while True:
        if sps_parser_read_bits(buffer, 1) == 0:
            bitcount += 1
        else:
            break

    result = 0
    if bitcount:
        val = sps_parser_read_bits(buffer, bitcount)
        result = (1 << bitcount) - 1 + val

    return result


def sps_parser_read_eg(buffer):
    value = sps_parser_read_ueg(buffer)
    if value & 0x01:
        return (value + 1) // 2
    else:
        return -(value // 2)


def sps_parser_skipScalingList(buffer, count):
    deltaScale, lastScale, nextScale = 0, 8, 8
    for j in range(count):
        if nextScale != 0:
            deltaScale = sps_parser_read_eg(buffer)
            nextScale = (lastScale + deltaScale + 256) % 256
        lastScale = lastScale if nextScale == 0 else nextScale


def sps_parser(buffer):
    global sps_parser_offset
    profileIdc = 0
    pict_order_cnt_type = 0
    picWidthInMbsMinus1 = 0
    picHeightInMapUnitsMinus1 = 0
    frameMbsOnlyFlag = 0
    frameCropLeftOffset = 0
    frameCropRightOffset = 0
    frameCropTopOffset = 0
    frameCropBottomOffset = 0

    sps_parser_offset = 0
    buffer = base64.b64decode(buffer)  # 使用python内置的base64模块进行解码
    sps_parser_read_bits(buffer, 8)
    profileIdc = sps_parser_read_bits(buffer, 8)
    sps_parser_read_bits(buffer, 16)
    sps_parser_read_ueg(buffer)

    if profileIdc in [100, 110, 122, 244, 44, 83, 86, 118, 128]:
        chromaFormatIdc = sps_parser_read_ueg(buffer)
        if chromaFormatIdc == 3:
            sps_parser_read_bits(buffer, 1)
        sps_parser_read_ueg(buffer)
        sps_parser_read_ueg(buffer)
        sps_parser_read_bits(buffer, 1)
        if sps_parser_read_bits(buffer, 1):
            for i in range(8 if chromaFormatIdc != 3 else 12):
                if sps_parser_read_bits(buffer, 1):
                    if i < 6:
                        sps_parser_skipScalingList(buffer, 16)
                    else:
                        sps_parser_skipScalingList(buffer, 64)

    sps_parser_read_ueg(buffer)
    pict_order_cnt_type = sps_parser_read_ueg(buffer)

    if pict_order_cnt_type == 0:
        sps_parser_read_ueg(buffer)
    elif pict_order_cnt_type == 1:
        sps_parser_read_bits(buffer, 1)
        sps_parser_read_eg(buffer)
        sps_parser_read_eg(buffer)
        for i in range(sps_parser_read_ueg(buffer)):
            sps_parser_read_eg(buffer)

    sps_parser_read_ueg(buffer)
    sps_parser_read_bits(buffer, 1)
    picWidthInMbsMinus1 = sps_parser_read_ueg(buffer)
    picHeightInMapUnitsMinus1 = sps_parser_read_ueg(buffer)
    frameMbsOnlyFlag = sps_parser_read_bits(buffer, 1)
    if not frameMbsOnlyFlag:
        sps_parser_read_bits(buffer, 1)
    sps_parser_read_bits(buffer, 1)
    if sps_parser_read_bits(buffer, 1):
        frameCropLeftOffset = sps_parser_read_ueg(buffer)
        frameCropRightOffset = sps_parser_read_ueg(buffer)
        frameCropTopOffset = sps_parser_read_ueg(buffer)
        frameCropBottomOffset = sps_parser_read_ueg(buffer)

    return (
        ((picWidthInMbsMinus1 + 1) * 16)
        - frameCropLeftOffset * 2
        - frameCropRightOffset * 2
    ) << 16 | ((2 - frameMbsOnlyFlag) * (picHeightInMapUnitsMinus1 + 1) * 16) - (
        (frameMbsOnlyFlag if 2 else 4) * (frameCropTopOffset + frameCropBottomOffset)
    )


if __name__ == "__main__":
    buffer = "Z2QAH6zZAFAFumoMAgyAAAADAIAAABlHjBjL"
    print(base64.b64decode(buffer))
    dimensions = sps_parser(buffer)
    # 1280x720
    print(f"width = {dimensions >> 16}\nheight = {dimensions & 0xFFFF}")

    buffer = "J00AH41qCwEmhAAAAwAEAAADAMoQ"
    dimensions = sps_parser(buffer)
    # 704x576
    print(f"width = {dimensions >> 16}\nheight = {dimensions & 0xFFFF}")

    buffer = "J00AH41qCwPaEAAAAwAQAAADAyhA"
    dimensions = sps_parser(buffer)
    # 704x480
    print(f"width = {dimensions >> 16}\nheight = {dimensions & 0xFFFF}")
