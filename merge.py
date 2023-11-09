import cv2
import os
import numpy as np

# 如果有生成的merged_image.jpg文件，先删除
if os.path.exists("merged_image.jpg"):
    os.remove("merged_image.jpg")


def merge_images(image_paths, print_texts, images_per_row):
    # 获取所有图片的大小
    image_sizes = [cv2.imread(image_path).shape[:2] for image_path in image_paths]

    # 计算拼接后的图片的大小
    merged_image_height = max(image_sizes, key=lambda x: x[0])[0] * (
        (len(image_paths) - 1) // images_per_row + 1
    )
    merged_image_width = max(image_sizes, key=lambda x: x[1])[1] * images_per_row

    # 创建一个空白的图片
    merged_image = np.zeros(
        (merged_image_height, merged_image_width, 3), dtype=np.uint8
    )

    # 遍历图片路径列表
    for i, image_path in enumerate(image_paths):
        # 读取图片
        image = cv2.imread(image_path)

        # 在图片的右下角写上图片的文件名
        cv2.putText(
            image,
            print_texts[i],
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            8,
        )
        cv2.putText(
            image,
            print_texts[i],
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            2,
        )

        # 将图片拼接到空白的图片上
        row = i // images_per_row
        col = i % images_per_row
        merged_image[
            row * image.shape[0] : (row + 1) * image.shape[0],
            col * image.shape[1] : (col + 1) * image.shape[1],
        ] = image

    cv2.imwrite("merged_image.jpg", merged_image)


