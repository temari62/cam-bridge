"""
CamBridge - virtual background for Send mode (blur or replace the room behind you).

The person is separated from the background by the PP-HumanSeg model from the OpenCV
Zoo (models/pphumanseg.onnx, Apache-2.0, see models/SOURCE.txt). It runs on the CPU
through OpenCV's own DNN module, so no extra Python packages are needed: about 10 ms
of segmentation plus 10 ms of compositing per 720p frame on a laptop CPU.

Usage (sender.py applies it to every frame before encoding):
    bg = create("blur", blur="strong")              # blur the room
    bg = create("image", image=r"C:\\pics\\beach.jpg")  # replace the room
    frame = bg.apply(frame)                          # BGR in -> BGR out, same size
"""

import os
import sys

import cv2
import numpy as np

MODES = ("off", "blur", "image")
# Blur strength -> Gaussian sigma applied at quarter resolution (cheap and bokeh-like).
BLUR_LEVELS = {"light": 3, "medium": 6, "strong": 10}
IMAGE_TYPES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

MODEL_FILE = "pphumanseg.onnx"
MODEL_INPUT = 192          # the model takes a 192x192 RGB square
MODEL_MEAN = 127.5         # pixels are scaled to [-1, 1]
EDGE_FEATHER = 3           # sigma (px) that softens the person outline at full size
TEMPORAL_SMOOTHING = 0.5   # weight of the previous frame's mask (0 = none, <1)


def model_path():
    """Path of the segmentation model: next to this file, or inside the PyInstaller bundle."""
    candidates = []
    base = getattr(sys, "_MEIPASS", "")
    if base:
        candidates.append(os.path.join(base, "models", MODEL_FILE))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "models", MODEL_FILE))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return candidates[-1]


def available():
    """True when the segmentation model is present (the feature can be offered)."""
    return os.path.isfile(model_path())


def load_image(path):
    """Read a background picture as BGR. Unicode-safe on Windows (cv2.imread is not)."""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"background image not found: {path}")
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"not a readable picture (jpg/png/bmp/webp): {path}")
    return img


def cover(img, width, height):
    """Scale and centre-crop img so it fills width x height without distortion."""
    h, w = img.shape[:2]
    scale = max(width / w, height / h)
    nw, nh = max(width, int(round(w * scale))), max(height, int(round(h * scale)))
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    x0, y0 = (nw - width) // 2, (nh - height) // 2
    return np.ascontiguousarray(img[y0:y0 + height, x0:x0 + width])


def create(mode="off", image=None, blur="medium"):
    """Build a VirtualBackground for the settings, or None when mode is 'off'.

    Raises FileNotFoundError / ValueError for a bad picture or a missing model, so the
    caller can show the problem before streaming starts."""
    mode = (mode or "off").lower()
    if mode not in MODES:
        raise ValueError(f"unknown background mode '{mode}' (use {', '.join(MODES)})")
    if mode == "off":
        return None
    return VirtualBackground(mode, image=image, blur=blur)


class VirtualBackground:
    def __init__(self, mode, image=None, blur="medium"):
        if not available():
            raise FileNotFoundError(f"segmentation model missing: {model_path()}")
        if blur not in BLUR_LEVELS:
            raise ValueError(f"unknown blur strength '{blur}' (use {', '.join(BLUR_LEVELS)})")
        self.mode = mode
        self.blur = blur
        self.image_path = image
        self._sigma = BLUR_LEVELS[blur]
        self._net = cv2.dnn.readNet(model_path())
        self._image = load_image(image) if mode == "image" else None
        self._bg = None          # image mode: the picture fitted to the frame size
        self._bg_size = None
        self._prev = None        # previous mask, for temporal smoothing

    def describe(self):
        if self.mode == "image":
            return f"image ({os.path.basename(self.image_path)})"
        return f"blur ({self.blur})"

    # --- pipeline -----------------------------------------------------------------
    def _segment(self, frame):
        """Person probability per pixel, MODEL_INPUT x MODEL_INPUT float32 in [0, 1]."""
        small = cv2.resize(frame, (MODEL_INPUT, MODEL_INPUT), interpolation=cv2.INTER_AREA)
        blob = cv2.dnn.blobFromImage(small, scalefactor=1.0 / MODEL_MEAN,
                                     mean=(MODEL_MEAN, MODEL_MEAN, MODEL_MEAN), swapRB=True)
        self._net.setInput(blob)
        out = self._net.forward()          # 1 x 2 x H x W, softmax over the 2 classes
        return np.ascontiguousarray(out[0, 1], dtype=np.float32)

    def _background(self, frame):
        h, w = frame.shape[:2]
        if self.mode == "image":
            if self._bg is None or self._bg_size != (w, h):
                self._bg = cover(self._image, w, h)
                self._bg_size = (w, h)
            return self._bg
        # Blur: shrink, blur, enlarge. Far cheaper than a huge kernel at full size.
        small = cv2.resize(frame, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), self._sigma)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

    def apply(self, frame):
        """Return the frame with the room blurred/replaced; the person is kept as is."""
        m = self._segment(frame)
        if self._prev is not None and self._prev.shape == m.shape:
            m = cv2.addWeighted(m, 1.0 - TEMPORAL_SMOOTHING, self._prev, TEMPORAL_SMOOTHING, 0)
        self._prev = m
        h, w = frame.shape[:2]
        mask = cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)
        mask = cv2.GaussianBlur(mask, (0, 0), EDGE_FEATHER)
        return cv2.blendLinear(frame, self._background(frame), mask, 1.0 - mask)


def main():
    """Quick check from the command line: python background.py photo.jpg [blur|image] [bg.jpg]"""
    import argparse
    import time
    p = argparse.ArgumentParser(description="Try the virtual background on a picture")
    p.add_argument("photo", help="a picture of a person (jpg/png)")
    p.add_argument("--mode", choices=("blur", "image"), default="blur")
    p.add_argument("--image", help="background picture for --mode image")
    p.add_argument("--blur", choices=tuple(BLUR_LEVELS), default="medium")
    p.add_argument("--out", default="background_out.jpg")
    a = p.parse_args()
    bg = create(a.mode, image=a.image, blur=a.blur)
    frame = load_image(a.photo)
    bg.apply(frame)  # warm-up
    t = time.perf_counter()
    n = 20
    for _ in range(n):
        out = bg.apply(frame)
    print(f"{bg.describe()}: {(time.perf_counter() - t) / n * 1000:.1f} ms per "
          f"{frame.shape[1]}x{frame.shape[0]} frame -> {a.out}")
    cv2.imwrite(a.out, out)


if __name__ == "__main__":
    main()
