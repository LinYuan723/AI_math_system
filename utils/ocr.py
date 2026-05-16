"""OCR utility using rapidocr-onnxruntime for text extraction from images."""
from rapidocr_onnxruntime import RapidOCR
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io

_engine = None

def get_ocr_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Extract text from image bytes using RapidOCR with enhanced preprocessing."""
    img = Image.open(io.BytesIO(image_bytes))

    # 转为灰度
    img_gray = img.convert('L')

    # 自动对比度增强
    img_gray = ImageOps.autocontrast(img_gray, cutoff=2)

    # 增强对比度和锐化
    enhancer = ImageEnhance.Contrast(img_gray)
    img_gray = enhancer.enhance(2.0)
    img_gray = img_gray.filter(ImageFilter.SHARPEN)

    # 大图缩小以提高OCR速度和质量
    w, h = img_gray.size
    max_dim = 2048
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img_gray = img_gray.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    engine = get_ocr_engine()
    result, _ = engine(np.array(img_gray))

    if result is None:
        return ""

    lines = []
    for item in result:
        box, text, conf = item
        try:
            conf = float(conf)
        except (ValueError, TypeError):
            conf = 0.0
        # 降低中文文字置信度门槛
        if conf < 0.25:
            continue
        try:
            y_center = (float(box[0][1]) + float(box[2][1])) / 2
            x_left = float(box[0][0])
        except (ValueError, TypeError, IndexError):
            continue
        lines.append((y_center, x_left, text.strip(), conf))

    if not lines:
        return ""

    # 按行排列（容差更大，适应多行排版）
    lines.sort(key=lambda item: (round(item[0] / 25), item[1]))
    return "\n".join(item[2] for item in lines)
