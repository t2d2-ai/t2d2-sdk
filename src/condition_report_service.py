import logging
import math
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Dict, Tuple, Union
import os
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

if not logger.handlers:
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(_log_handler)
    logger.setLevel(logging.INFO)


# T2D2 image-annotation shape IDs (portal / API).
T2D2_SHAPE_POLYLINE = 2
T2D2_SHAPE_RECTANGLE = 3
T2D2_SHAPE_POLYGON = 4
T2D2_SHAPE_LINE = 5
T2D2_SHAPE_CIRCLE = 6
T2D2_SHAPE_ELLIPSE = 7
T2D2_SHAPE_POINT = 8

_T2D2_KNOWN_SHAPE_STYLES = {
    T2D2_SHAPE_POLYLINE: "polyline",
    T2D2_SHAPE_RECTANGLE: "rectangle",
    T2D2_SHAPE_POLYGON: "polygon",
    T2D2_SHAPE_LINE: "line",
    T2D2_SHAPE_CIRCLE: "circle",
    T2D2_SHAPE_ELLIPSE: "ellipse",
    T2D2_SHAPE_POINT: "point",
}

# Point / polyline / line are drawn as edge callout arrows, not raw geometry.
_ARROW_CALLOUT_STYLES = frozenset({"point", "polyline", "line"})

# Rectangle, polygon, circle, ellipse: outline only (no interior fill).
_OUTLINE_ONLY_STYLES = frozenset({"rectangle", "polygon", "circle", "ellipse"})


def pil_image_to_jpeg_bytes(
    img: Image.Image, quality: int = 93, subsampling: int = 0
) -> io.BytesIO:
    """
    Encode a PIL image as JPEG for embedding in documents (smaller than PNG).
    subsampling: 0 = 4:4:4 (largest), 2 = 4:2:0 (smaller files, fine at report display size).
    """
    work = img
    if work.mode in ("RGBA", "LA"):
        background = Image.new("RGB", work.size, (255, 255, 255))
        alpha = work.split()[-1]
        background.paste(work, mask=alpha)
        work = background
    elif work.mode == "P":
        work = work.convert("RGBA")
        background = Image.new("RGB", work.size, (255, 255, 255))
        background.paste(work, mask=work.split()[-1])
        work = background
    elif work.mode != "RGB":
        work = work.convert("RGB")
    buf = io.BytesIO()
    try:
        work.save(
            buf,
            format="JPEG",
            quality=quality,
            optimize=True,
            subsampling=subsampling,
            progressive=True,
        )
    except TypeError:
        buf = io.BytesIO()
        try:
            work.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        except TypeError:
            buf = io.BytesIO()
            work.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return buf


def resize_pil_to_fit_box(img: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """
    Downscale so the image fits within max_width x max_height while preserving aspect ratio.
    Used so embedded JPEGs match on-page display size (keeps .docx small).
    """
    if max_width <= 0 or max_height <= 0:
        return img
    w, h = img.size
    if w <= max_width and h <= max_height:
        return img
    scale = min(max_width / float(w), max_height / float(h))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # type: ignore[attr-defined]
    return img.resize((nw, nh), resample)


def resize_pil_max_long_edge(img: Image.Image, max_long_edge: int) -> Image.Image:
    """Downscale so max(width, height) <= max_long_edge (no upscale)."""
    if max_long_edge <= 0:
        return img
    w, h = img.size
    if max(w, h) <= max_long_edge:
        return img
    scale = max_long_edge / float(max(w, h))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # type: ignore[attr-defined]
    return img.resize((nw, nh), resample)


class ImageAnnotationCropper:
    def __init__(self, image_data_list: Union[dict, List[dict]]):
        """
        Initialize with single image data or list of image data containing annotations.
        """
        logger.info(f"Initializing ImageAnnotationCropper...")
        if isinstance(image_data_list, dict):
            logger.info(f"Converting single dict to list format")
            image_data_list = [image_data_list]
        self.image_data_list = image_data_list
        self.images = []  # Will store (image_data, PIL_Image) tuples
        logger.info(f"Initialized with {len(self.image_data_list)} image(s)")

    def download_images(self):
        """Download all images from URLs"""
        logger.info(f"Starting download of {len(self.image_data_list)} images...")
        for idx, image_data in enumerate(self.image_data_list):
            try:
                logger.info(f"Downloading image {idx+1}/{len(self.image_data_list)}...")
                response = requests.get(image_data['url'])
                response.raise_for_status()
                _prev_max_pixels = getattr(Image, "MAX_IMAGE_PIXELS", None)
                try:
                    Image.MAX_IMAGE_PIXELS = None
                    pil_image = Image.open(io.BytesIO(response.content))
                    pil_image.load()
                finally:
                    Image.MAX_IMAGE_PIXELS = _prev_max_pixels
                try:
                    from PIL import ImageOps
                    pil_image = ImageOps.exif_transpose(pil_image)
                except Exception:
                    pass
                self._sync_working_dimensions(image_data, pil_image)
                self.images.append((image_data, pil_image))
                aw, ah = pil_image.size
                logger.info(f"✓ [{idx+1}/{len(self.image_data_list)}] Downloaded: {aw}x{ah} ({len(response.content)} bytes)")
            except Exception as e:
                logger.error(f"✗ [{idx+1}/{len(self.image_data_list)}] Error downloading image: {e}")
                self.images.append((image_data, None))
        successful = sum(1 for _, img in self.images if img is not None)
        logger.info(f"✓ Download complete: {successful}/{len(self.image_data_list)} images successfully downloaded\n")
        return self.images

    def downscale_images_for_report(
        self,
        max_long_edge: Union[int, None] = 4096,
        max_megapixels: Union[float, None] = 45.0,
    ) -> None:
        if max_long_edge is None and max_megapixels is None:
            for idx, (image_data, pil_image) in enumerate(self.images):
                if pil_image is None:
                    continue
                image_data["crop_source_image"] = pil_image
                self._sync_working_dimensions(image_data, pil_image)
            return
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS  # type: ignore[attr-defined]
        for idx, (image_data, pil_image) in enumerate(self.images):
            if pil_image is None:
                continue
            w, h = pil_image.size
            scale = 1.0
            if max_long_edge is not None and max(w, h) > max_long_edge:
                scale = min(scale, max_long_edge / float(max(w, h)))
            if max_megapixels is not None:
                mp = (w * h) / 1_000_000.0
                if mp > max_megapixels:
                    scale = min(scale, math.sqrt(max_megapixels / mp))
            # Keep full-resolution PIL for detail crops; downscaled copy for overview only.
            image_data["crop_source_image"] = pil_image
            if scale >= 0.999:
                self._sync_working_dimensions(image_data, pil_image)
                continue
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            resized = pil_image.resize((new_w, new_h), resample)
            self.images[idx] = (image_data, resized)
            self._sync_working_dimensions(image_data, resized)
            logger.info(f"Downscaled for report: {w}x{h} -> {new_w}x{new_h} (scale {scale:.4f})")

    def release_crop_source_images(self) -> None:
        """Free full-resolution references after all crops for an image are done."""
        for image_data, _ in self.images:
            image_data.pop("crop_source_image", None)

    @staticmethod
    def scale_bbox_to_working(
        bbox: Tuple[int, int, int, int],
        source_width: int,
        source_height: int,
        working_width: int,
        working_height: int,
    ) -> Tuple[int, int, int, int]:
        """Map a crop box from source/full pixels to the downscaled overview image."""
        if not bbox or source_width <= 0 or source_height <= 0:
            return bbox
        sx = working_width / float(source_width)
        sy = working_height / float(source_height)
        x0, y0, x1, y1 = bbox
        return (
            int(round(x0 * sx)),
            int(round(y0 * sy)),
            int(round(x1 * sx)),
            int(round(y1 * sy)),
        )

    @staticmethod
    def _aspect_ratio(width: int, height: int) -> float:
        return width / float(height) if height else 0.0

    def _annotation_space_dimensions(self, image_data: dict):
        space = image_data.get("annotation_space") or {}
        info = image_data.get("info") or {}
        width = space.get("width") or info.get("width")
        height = space.get("height") or info.get("height")
        try:
            w = int(width) if width is not None else None
            h = int(height) if height is not None else None
        except (TypeError, ValueError):
            return None, None
        if w and w > 0 and h and h > 0:
            return w, h
        return None, None

    def _sync_working_dimensions(self, image_data: dict, pil_image: Image.Image) -> None:
        """Keep info/working dimensions aligned with the decoded pixels we draw on."""
        w, h = pil_image.size
        image_data.setdefault("info", {})
        image_data["info"]["width"] = w
        image_data["info"]["height"] = h
        ref_w, ref_h = self._annotation_space_dimensions(image_data)
        if ref_w and ref_h:
            pil_ar = self._aspect_ratio(w, h)
            ref_ar = self._aspect_ratio(ref_w, ref_h)
            if ref_ar > 0 and abs(pil_ar - ref_ar) / ref_ar > 0.02:
                swap_ar = self._aspect_ratio(ref_h, ref_w)
                if swap_ar > 0 and abs(pil_ar - swap_ar) / swap_ar <= 0.02:
                    logger.warning(
                        "Image %s: annotation space %sx%s vs file %sx%s — using transposed "
                        "coordinate mapping",
                        image_data.get("image_id"),
                        ref_w, ref_h, w, h,
                    )
                    image_data["coordinate_transpose"] = True
                else:
                    logger.warning(
                        "Image %s: annotation aspect %.3f differs from file %.3f "
                        "(space %sx%s, file %sx%s)",
                        image_data.get("image_id"),
                        ref_ar, pil_ar, ref_w, ref_h, w, h,
                    )
        image_data["working_width"] = w
        image_data["working_height"] = h

    def working_dimensions(self, image_data: dict, pil_image: Image.Image) -> Tuple[int, int]:
        """Return (width, height) for denormalizing annotation coordinates."""
        if pil_image is not None:
            w, h = pil_image.size
            if image_data.get("working_width") != w or image_data.get("working_height") != h:
                self._sync_working_dimensions(image_data, pil_image)
            return w, h
        w = image_data.get("working_width") or (image_data.get("info") or {}).get("width")
        h = image_data.get("working_height") or (image_data.get("info") or {}).get("height")
        return int(w), int(h)

    def flatten_points(self, points: Union[List[float], List[List[float]]]) -> List[float]:
        """
        Flatten nested point lists into a single flat list.
        Handles both [x1, y1, x2, y2] and [[x1, y1], [x2, y2]] formats.

        flatten_points preserves API order; use _reorder_points_for_shape
        before denormalizing (shape-specific [y, x] vs [x, y] conventions).
        """
        flat_points = []
        for point in points:
            if isinstance(point, (list, tuple)):
                flat_points.extend(point)
            else:
                flat_points.append(point)
        return flat_points

    @staticmethod
    def _shape_key(shape) -> Union[int, None]:
        if shape is None:
            return None
        try:
            return int(shape)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _reorder_yx_to_xy(flat_points: List[float]) -> List[float]:
        """
        Swap consecutive pairs from [row_norm, col_norm] to [col_norm, row_norm]
        i.e. [y, x] -> [x, y] for each vertex/corner.
        """
        if len(flat_points) % 2 != 0:
            return flat_points  # malformed; leave unchanged
        reordered = []
        for i in range(0, len(flat_points), 2):
            y_val = flat_points[i]
            x_val = flat_points[i + 1]
            reordered.extend([x_val, y_val])
        return reordered

    def _reorder_points_for_shape(
        self,
        flat_points: List[float],
        shape,
        is_nested: bool,
    ) -> List[float]:
        """
        Normalize API point order to [x, y, ...] before denormalizing.

        T2D2 uses inconsistent storage across shape types on orthomosaics:
        - Shape 2/5 nested (polyline, line): [[y, x], ...]
        - Shape 3 flat (rectangle): [y0, x0, y1, x1]
        - Shape 4 nested (polygon): [[x, y], ...] (no swap)
        """
        shape_key = self._shape_key(shape)
        if shape_key in (T2D2_SHAPE_POLYLINE, T2D2_SHAPE_LINE):
            return self._reorder_yx_to_xy(flat_points)
        if shape_key == T2D2_SHAPE_RECTANGLE:
            return self._reorder_yx_to_xy(flat_points)
        if shape_key == T2D2_SHAPE_POLYGON:
            return flat_points
        if is_nested:
            return self._reorder_yx_to_xy(flat_points)
        return flat_points

    @staticmethod
    def _is_nested_points(points) -> bool:
        return bool(points) and isinstance(points[0], (list, tuple))

    def _count_vertices(self, points) -> int:
        if not points:
            return 0
        if self._is_nested_points(points):
            return len(points)
        flat = self.flatten_points(points)
        return len(flat) // 2

    @staticmethod
    def _path_is_thin(coords_list: List[Tuple[float, float]], aspect_threshold: float = 4.0) -> bool:
        if len(coords_list) < 2:
            return False
        xs = [c[0] for c in coords_list]
        ys = [c[1] for c in coords_list]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if w <= 0 and h <= 0:
            return False
        if w <= 0 or h <= 0:
            return True
        return max(w, h) / min(w, h) >= aspect_threshold

    def _normalized_coords_list(
        self, points, shape=None
    ) -> List[Tuple[float, float]]:
        if not points:
            return []
        is_nested = self._is_nested_points(points)
        flat = self.flatten_points(points)
        if len(flat) % 2:
            flat = flat[:-1]
        flat = self._reorder_points_for_shape(flat, shape, is_nested)
        return [
            (float(flat[i]), float(flat[i + 1]))
            for i in range(0, len(flat) - 1, 2)
        ]

    def _infer_draw_style(self, points) -> str:
        """Infer render style from point layout when shape id is missing or unknown."""
        n = self._count_vertices(points)
        nested = self._is_nested_points(points)
        flat = self.flatten_points(points)

        if n <= 1 or len(flat) <= 2:
            return "point"
        if not nested and len(flat) == 4:
            return "rectangle"
        if not nested and len(flat) == 3:
            return "circle"
        if nested:
            norm_coords = self._normalized_coords_list(points)
            if n == 2:
                return "line"
            if self._path_is_thin(norm_coords):
                return "polyline"
            return "polygon"
        if n == 2:
            return "line"
        if n >= 3:
            return "polygon"
        return "polyline"

    def _resolve_annotation_draw_style(self, shape, points) -> str:
        """Map API shape id + points to a concrete draw style."""
        shape_key = None
        if shape is not None:
            try:
                shape_key = int(shape)
            except (TypeError, ValueError):
                shape_key = None
        if shape_key in _T2D2_KNOWN_SHAPE_STYLES:
            style = _T2D2_KNOWN_SHAPE_STYLES[shape_key]
            if style == "rectangle" and self._is_nested_points(points) and self._count_vertices(points) >= 3:
                return "polygon"
            return style
        return self._infer_draw_style(points)

    def _render_annotation_geometry(
        self,
        draw: ImageDraw.ImageDraw,
        style: str,
        pixel_coords: List[int],
        coords_list: List[Tuple[int, int]],
        outline_color: Tuple[int, int, int, int],
        fill_color: Tuple[int, int, int, int],
        image_width: int,
        image_height: int,
        canvas_width: int = None,
        canvas_height: int = None,
    ) -> None:
        """Draw annotation geometry for any supported or inferred style."""
        cw = canvas_width if canvas_width is not None else image_width
        ch = canvas_height if canvas_height is not None else image_height
        if style in _ARROW_CALLOUT_STYLES:
            target = self._annotation_callout_target(style, coords_list)
            if target is not None:
                self._draw_callout_arrow_to_target(
                    draw, cw, ch, target, outline_color, line_width=5, head_len=22.0
                )
            return
        outline_fill = None if style in _OUTLINE_ONLY_STYLES else fill_color
        if style == "rectangle" and len(pixel_coords) >= 4:
            xs = [pixel_coords[0], pixel_coords[2]]
            ys = [pixel_coords[1], pixel_coords[3]]
            draw.rectangle(
                [(min(xs), min(ys)), (max(xs), max(ys))],
                outline=outline_color,
                fill=outline_fill,
                width=3,
            )
            return
        if style == "polygon" and len(coords_list) >= 3:
            draw.polygon(coords_list, outline=outline_color, fill=outline_fill, width=3)
            return
        if style in ("circle", "ellipse"):
            if len(pixel_coords) >= 6:
                xs = pixel_coords[0::2]; ys = pixel_coords[1::2]
                draw.ellipse(
                    [(min(xs), min(ys)), (max(xs), max(ys))],
                    outline=outline_color,
                    fill=outline_fill,
                    width=3,
                )
                return
            if len(pixel_coords) >= 4:
                xs = pixel_coords[0::2]; ys = pixel_coords[1::2]
                draw.ellipse(
                    [(min(xs), min(ys)), (max(xs), max(ys))],
                    outline=outline_color,
                    fill=outline_fill,
                    width=3,
                )
                return
            if len(pixel_coords) >= 3:
                cx, cy, r = pixel_coords[0], pixel_coords[1], pixel_coords[2]
                if r <= 1:
                    r = int(round(r * min(image_width, image_height)))
                r = max(3, int(r))
                draw.ellipse(
                    [(cx - r, cy - r), (cx + r, cy + r)],
                    outline=outline_color,
                    fill=outline_fill,
                    width=3,
                )
                return
        if len(coords_list) >= 3:
            draw.polygon(coords_list, outline=outline_color, fill=None, width=3)
        elif len(coords_list) >= 2:
            draw.line(coords_list, fill=outline_color, width=4)
        elif len(coords_list) >= 1:
            cx, cy = coords_list[0]; radius = 15
            draw.ellipse(
                [(cx - radius, cy - radius), (cx + radius, cy + radius)],
                outline=outline_color,
                fill=None,
                width=3,
            )

    def _coordinates_are_normalized(self, flat_points: List[float]) -> bool:
        if not flat_points:
            return True
        try:
            vals = [float(v) for v in flat_points]
        except (TypeError, ValueError):
            return True
        return max(abs(v) for v in vals) <= 1.5

    def denormalize_coordinates(
        self,
        normalized_points: Union[List[float], List[List[float]]],
        image_width: int,
        image_height: int,
        image_data: dict = None,
        shape=None,
    ) -> List[int]:
        """
        Convert normalized coordinates to pixel coordinates on the working image.

        Point order is normalized per shape via _reorder_points_for_shape before
        scaling to pixel space.
        """
        is_nested = self._is_nested_points(normalized_points)
        flat_points = self.flatten_points(normalized_points)

        if len(flat_points) % 2 != 0:
            logger.warning(
                "Odd number of coordinate values: %s, truncating last value",
                len(flat_points),
            )
            flat_points = flat_points[:-1]

        flat_points = self._reorder_points_for_shape(flat_points, shape, is_nested)

        use_normalized = self._coordinates_are_normalized(flat_points)
        ref_w, ref_h = image_width, image_height
        if image_data and not use_normalized:
            ref_w, ref_h = self._annotation_space_dimensions(image_data) or (ref_w, ref_h)
            if not ref_w or not ref_h:
                ref_w, ref_h = image_width, image_height

        transpose = bool(image_data and image_data.get("coordinate_transpose"))
        pixel_coords = []
        for i in range(0, len(flat_points), 2):
            if i + 1 >= len(flat_points):
                break
            x_in = float(flat_points[i])
            y_in = float(flat_points[i + 1])
            if use_normalized:
                x_norm = max(0.0, min(1.0, x_in))
                y_norm = max(0.0, min(1.0, y_in))
                if transpose:
                    x = int(round(y_norm * image_width))
                    y = int(round((1.0 - x_norm) * image_height))
                else:
                    x = int(round(x_norm * image_width))
                    y = int(round(y_norm * image_height))
            else:
                if transpose:
                    x = int(round(y_in * image_width / float(ref_h)))
                    y = int(round((ref_w - x_in) * image_height / float(ref_w)))
                else:
                    x = int(round(x_in * image_width / float(ref_w)))
                    y = int(round(y_in * image_height / float(ref_h)))
            pixel_coords.extend([x, y])
        return pixel_coords

    def get_bounding_box(
        self,
        points: Union[List[float], List[List[float]]],
        image_width: int,
        image_height: int,
        image_data: dict = None,
        shape=None,
    ) -> Tuple[int, int, int, int]:
        """
        Get bounding box from annotation points.
        Returns: (x_min, y_min, x_max, y_max) inclusive pixel indices.
        """
        pixel_coords = self.denormalize_coordinates(
            points, image_width, image_height, image_data=image_data, shape=shape
        )
        if len(pixel_coords) < 2:
            logger.warning(f"Insufficient coordinates for bounding box: {len(pixel_coords)}")
            return None
        x_coords = [pixel_coords[i] for i in range(0, len(pixel_coords), 2)]
        y_coords = [pixel_coords[i] for i in range(1, len(pixel_coords), 2)]
        if not x_coords or not y_coords:
            return None
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        x_min = max(0, min(x_min, image_width - 1))
        y_min = max(0, min(y_min, image_height - 1))
        x_max = max(0, min(x_max, image_width - 1))
        y_max = max(0, min(y_max, image_height - 1))
        return (x_min, y_min, x_max, y_max)

    @staticmethod
    def _pil_crop_box(bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """PIL crop expects exclusive right/bottom edges."""
        x_min, y_min, x_max, y_max = bbox
        return (x_min, y_min, x_max + 1, y_max + 1)

    def expand_bbox(self, bbox, image_width, image_height, padding_percent=0.2, min_size=50):
        x_min, y_min, x_max, y_max = bbox
        width = x_max - x_min
        height = y_max - y_min
        if width < min_size:
            center_x = (x_min + x_max) // 2
            x_min = center_x - min_size // 2
            x_max = center_x + min_size // 2
            width = min_size
        if height < min_size:
            center_y = (y_min + y_max) // 2
            y_min = center_y - min_size // 2
            y_max = center_y + min_size // 2
            height = min_size
        padding_x = int(width * padding_percent)
        padding_y = int(height * padding_percent)
        x_min = max(0, x_min - padding_x)
        y_min = max(0, y_min - padding_y)
        x_max = min(image_width, x_max + padding_x)
        y_max = min(image_height, y_max + padding_y)
        return (x_min, y_min, x_max, y_max)

    def enforce_minimum_crop_extent(
        self,
        bbox,
        image_width,
        image_height,
        min_width_fraction=0.20,
        min_height_fraction=0.20,
        max_min_crop_width_px: Union[int, None] = None,
        max_min_crop_height_px: Union[int, None] = None,
    ):
        x_min, y_min, x_max, y_max = bbox
        bw = x_max - x_min
        bh = y_max - y_min
        min_w = max(1, int(image_width * min_width_fraction))
        min_h = max(1, int(image_height * min_height_fraction))
        if max_min_crop_width_px is not None:
            min_w = min(min_w, int(max_min_crop_width_px))
        if max_min_crop_height_px is not None:
            min_h = min(min_h, int(max_min_crop_height_px))
        target_w = min(image_width, max(bw, min_w))
        target_h = min(image_height, max(bh, min_h))
        cx = (x_min + x_max) // 2
        cy = (y_min + y_max) // 2
        nx_min = cx - target_w // 2
        ny_min = cy - target_h // 2
        nx_max = nx_min + target_w
        ny_max = ny_min + target_h
        if nx_min < 0:
            nx_max -= nx_min; nx_min = 0
        if nx_max > image_width:
            nx_min -= nx_max - image_width; nx_max = image_width
        nx_min = max(0, nx_min)
        if ny_min < 0:
            ny_max -= ny_min; ny_min = 0
        if ny_max > image_height:
            ny_min -= ny_max - image_height; ny_max = image_height
        ny_min = max(0, ny_min)
        return (int(nx_min), int(ny_min), int(nx_max), int(ny_max))

    def _flatten_rgba_to_rgb(self, rgba: Image.Image, bg=(255, 255, 255)) -> Image.Image:
        rgb = Image.new('RGB', rgba.size, bg)
        if rgba.mode == 'RGBA':
            rgb.paste(rgba, mask=rgba.split()[3])
        else:
            rgb.paste(rgba)
        return rgb

    def _draw_bold_rectangle_outline(self, draw, box, color, thickness=10, outer_color=(90, 12, 0, 255)):
        x0, y0, x1, y1 = box
        for i in range(thickness):
            stroke = outer_color if i < thickness - 3 else color
            draw.rectangle([x0-i, y0-i, x1+i, y1+i], outline=stroke, width=1)

    def _draw_arrow_line(self, draw, start, end, fill, line_width=4, head_len=22.0):
        draw.line([start, end], fill=fill, width=line_width)
        ang = math.atan2(end[1]-start[1], end[0]-start[0])
        p1 = (end[0]-head_len*math.cos(ang-0.45), end[1]-head_len*math.sin(ang-0.45))
        p2 = (end[0]-head_len*math.cos(ang+0.45), end[1]-head_len*math.sin(ang+0.45))
        draw.polygon([
            (int(round(end[0])), int(round(end[1]))),
            (int(round(p1[0])), int(round(p1[1]))),
            (int(round(p2[0])), int(round(p2[1]))),
        ], fill=fill)

    @staticmethod
    def _annotation_callout_target(
        style: str, coords_list: List[Tuple[int, int]]
    ) -> Union[Tuple[float, float], None]:
        if not coords_list:
            return None
        if style == "point" or len(coords_list) == 1:
            return (float(coords_list[0][0]), float(coords_list[0][1]))
        xs = [c[0] for c in coords_list]
        ys = [c[1] for c in coords_list]
        return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)

    def _draw_callout_arrow_to_target(
        self,
        draw: ImageDraw.ImageDraw,
        canvas_width: int,
        canvas_height: int,
        target: Tuple[float, float],
        color: Tuple[int, int, int, int],
        line_width: int = 5,
        head_len: float = 22.0,
    ) -> None:
        """Draw an arrow from the nearest image edge toward the annotation target."""
        cx, cy = target
        W, H = canvas_width, canvas_height
        margin = max(16, min(W, H) // 40)
        dists = [cy, H - cy, cx, W - cx]
        idx = min(range(4), key=lambda i: dists[i])
        if idx == 0:
            start = (max(margin, min(W - margin, cx)), margin)
        elif idx == 1:
            start = (max(margin, min(W - margin, cx)), H - margin)
        elif idx == 2:
            start = (margin, max(margin, min(H - margin, cy)))
        else:
            start = (W - margin, max(margin, min(H - margin, cy)))
        vx, vy = cx - start[0], cy - start[1]
        length = math.hypot(vx, vy)
        if length <= 8:
            radius = max(6, min(W, H) // 80)
            draw.ellipse(
                [
                    (int(round(cx - radius)), int(round(cy - radius))),
                    (int(round(cx + radius)), int(round(cy + radius))),
                ],
                outline=color,
                width=3,
            )
            return
        shorten = min(28.0, length * 0.08)
        unit_x, unit_y = vx / length, vy / length
        end = (cx - shorten * unit_x, cy - shorten * unit_y)
        self._draw_arrow_line(draw, start, end, color, line_width=line_width, head_len=head_len)

    def highlight_crop_callout_on_image(self, image: Image.Image, crop_bbox) -> Image.Image:
        x0, y0, x1, y1 = crop_bbox
        W, H = image.size
        cx = (x0+x1)/2.0; cy = (y0+y1)/2.0
        margin = max(24, min(W, H)//40)
        accent = (185, 35, 0, 255); tint = (200, 55, 0, 130)
        base = image.copy()
        if base.mode != 'RGBA':
            base = base.convert('RGBA')
        overlay = Image.new('RGBA', base.size, (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([x0, y0, x1, y1], fill=tint)
        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)
        frame_box = (max(0,x0-2), max(0,y0-2), min(W-1,x1+2), min(H-1,y1+2))
        self._draw_bold_rectangle_outline(draw, frame_box, accent, thickness=12, outer_color=(90,12,0,255))
        dists = [cy, H-cy, cx, W-cx]
        idx = min(range(4), key=lambda i: dists[i])
        if idx == 0: start = (max(margin, min(W-margin, cx)), margin)
        elif idx == 1: start = (max(margin, min(W-margin, cx)), H-margin)
        elif idx == 2: start = (margin, max(margin, min(H-margin, cy)))
        else: start = (W-margin, max(margin, min(H-margin, cy)))
        vx, vy = cx-start[0], cy-start[1]
        L = math.hypot(vx, vy)
        if L > 15:
            shorten = min(28.0, L*0.08)
            unit_x, unit_y = vx/L, vy/L
            end = (cx-shorten*unit_x, cy-shorten*unit_y)
            self._draw_arrow_line(draw, start, end, accent, line_width=5, head_len=22.0)
        return self._flatten_rgba_to_rgb(base)

    def crop_annotation(self, image, annotation, image_width, image_height,
                        padding_percent=0.2, min_crop_width_fraction=0.20,
                        min_crop_height_fraction=0.20, image_data=None):
        try:
            logger.debug("Cropping annotation %s", annotation["id"])
            points = annotation['points']
            bbox = self.get_bounding_box(
                points,
                image_width,
                image_height,
                image_data=image_data,
                shape=annotation.get('shape'),
            )
            if bbox is None:
                logger.warning(f"Invalid bounding box for annotation {annotation['id']}")
                return None, None
            expanded_bbox = self.expand_bbox(bbox, image_width, image_height, padding_percent)
            expanded_bbox = self.enforce_minimum_crop_extent(
                expanded_bbox, image_width, image_height,
                min_crop_width_fraction, min_crop_height_fraction)
            if expanded_bbox[2] <= expanded_bbox[0] or expanded_bbox[3] <= expanded_bbox[1]:
                return None, None
            cropped = image.crop(self._pil_crop_box(expanded_bbox))
            if cropped.size[0] == 0 or cropped.size[1] == 0:
                return None, None
            logger.info(f"Successfully cropped annotation {annotation['id']}, size: {cropped.size[0]}x{cropped.size[1]}")
            return cropped, expanded_bbox
        except Exception as e:
            logger.error(f"Failed to crop annotation {annotation['id']}: {e}")
            return None, None

    def draw_annotation_on_image(self, image, annotation, image_width, image_height,
                                  bbox=None, image_data=None):
        try:
            logger.debug("Drawing annotation %s on image (shape type: %s)", annotation["id"], annotation["shape"])
            img_copy = image.copy()
            draw = ImageDraw.Draw(img_copy, 'RGBA')
            points = annotation['points']
            shape = annotation['shape']
            color = annotation['annotation_class']['annotation_class_color']
            color_rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            fill_color = color_rgb + (80,)
            outline_color = color_rgb + (255,)
            pixel_coords = self.denormalize_coordinates(
                points, image_width, image_height, image_data=image_data, shape=shape
            )
            if bbox:
                x_offset, y_offset = bbox[0], bbox[1]
                pixel_coords = [
                    pixel_coords[i] - x_offset if i % 2 == 0 else pixel_coords[i] - y_offset
                    for i in range(len(pixel_coords))
                ]
            coords_list = [(pixel_coords[i], pixel_coords[i+1]) for i in range(0, len(pixel_coords), 2)]
            draw_style = self._resolve_annotation_draw_style(shape, points)
            if not coords_list and not pixel_coords:
                logger.warning("Annotation %s has no drawable coordinates (shape=%s)", annotation["id"], shape)
            else:
                cw, ch = img_copy.size
                self._render_annotation_geometry(
                    draw,
                    draw_style,
                    pixel_coords,
                    coords_list,
                    outline_color,
                    fill_color,
                    image_width,
                    image_height,
                    canvas_width=cw,
                    canvas_height=ch,
                )
            logger.debug("Successfully drew annotation %s", annotation["id"])
            return img_copy
        except Exception as e:
            logger.error(f"Failed to draw annotation {annotation['id']}: {e}")
            return image

    def create_visualization(self, output_path='annotation_crops.png', padding_percent=0.2):
        logger.info(f"Starting visualization creation...")
        if not self.images:
            self.download_images()
        for img_idx, (image_data, pil_image) in enumerate(self.images):
            if pil_image is None:
                logger.warning(f"Skipping image {img_idx+1} (download failed)")
                continue
            logger.info(f"Processing image {img_idx+1} for visualization...")
            image_width, image_height = self.working_dimensions(image_data, pil_image)
            annotations = image_data['annotations']
            visible_annotations = [ann for ann in annotations if ann.get('visible', True)]
            if not visible_annotations:
                logger.warning(f"No visible annotations found in image {img_idx+1}!")
                continue
            base_path = output_path.rsplit('.', 1)
            if len(base_path) == 2:
                img_output_path = f"{base_path[0]}_image_{img_idx+1}.{base_path[1]}"
            else:
                img_output_path = f"{output_path}_image_{img_idx+1}.png"
            output_dir = os.path.dirname(img_output_path) if os.path.dirname(img_output_path) else '.'
            os.makedirs(output_dir, exist_ok=True)
            successful_crops = []
            for ann in visible_annotations:
                cropped_img, crop_bbox = self.crop_annotation(
                    pil_image, ann, image_width, image_height, padding_percent, image_data=image_data)
                if cropped_img is not None and crop_bbox is not None:
                    successful_crops.append((ann, cropped_img, crop_bbox))
            if not successful_crops:
                logger.warning(f"No valid crops could be created for image {img_idx+1}!")
                continue
            cols = 3
            rows = 1 + ((len(successful_crops) + cols - 1) // cols)
            fig = plt.figure(figsize=(18, 5*rows))
            ax1 = plt.subplot(rows, cols, (1, cols))
            ax1.set_title(f'Image {img_idx+1}: Original with All Annotations', fontsize=16, fontweight='bold')
            original_with_annotations = pil_image.copy()
            for ann in visible_annotations:
                original_with_annotations = self.draw_annotation_on_image(
                    original_with_annotations, ann, image_width, image_height, image_data=image_data)
            ax1.imshow(original_with_annotations)
            ax1.axis('off')
            legend_items = [f"ID {ann['id']}: {ann['annotation_class']['annotation_class_long_name']}"
                            for ann, _, _ in successful_crops]
            legend_text = "Annotations:\n" + "\n".join(legend_items[:10])
            if len(legend_items) > 10:
                legend_text += f"\n... and {len(legend_items)-10} more"
            ax1.text(1.02, 0.5, legend_text, transform=ax1.transAxes, fontsize=9,
                     verticalalignment='center',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            for idx, (ann, cropped_img, crop_bbox) in enumerate(successful_crops):
                ax = plt.subplot(rows, cols, cols+idx+1)
                cropped_with_annotation = self.draw_annotation_on_image(
                    cropped_img, ann, image_width, image_height, crop_bbox, image_data=image_data)
                class_name = ann['annotation_class']['annotation_class_long_name']
                area = ann.get('area', 0)
                condition = ann.get('condition', {}).get('rating_name', 'N/A')
                title = f"ID: {ann['id']} - {class_name}"
                if area > 0: title += f"\nArea: {area:.1f} sq units"
                if condition != 'N/A': title += f"\nCondition: {condition}"
                ax.set_title(title, fontsize=10, fontweight='bold')
                ax.imshow(cropped_with_annotation)
                ax.axis('off')
            plt.tight_layout()
            logger.info(f"Saving visualization to {img_output_path}...")
            plt.savefig(img_output_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"Visualization saved to {img_output_path}\n")
        logger.info(f"Visualization creation complete")
        return True

    def save_individual_crops(self, output_dir='crops', padding_percent=0.2):
        logger.info(f"Starting to save individual crops to directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        if not self.images:
            self.download_images()
        total_saved = 0
        total_annotations = 0
        for img_idx, (image_data, pil_image) in enumerate(self.images):
            if pil_image is None:
                continue
            image_width, image_height = self.working_dimensions(image_data, pil_image)
            visible_annotations = [ann for ann in image_data['annotations'] if ann.get('visible', True)]
            total_annotations += len(visible_annotations)
            for ann in visible_annotations:
                cropped_img, bbox = self.crop_annotation(
                    pil_image, ann, image_width, image_height, padding_percent, image_data=image_data)
                if cropped_img is None or bbox is None:
                    continue
                cropped_with_annotation = self.draw_annotation_on_image(
                    cropped_img, ann, image_width, image_height, bbox, image_data=image_data)
                filename = f"{output_dir}/img{img_idx+1}_crop_{ann['id']}_{ann['annotation_class']['annotation_class_name']}.jpg"
                cropped_with_annotation.save(filename, quality=95)
                total_saved += 1
                logger.info(f"Saved: {filename}")
        logger.info(f"Total crops saved: {total_saved}/{total_annotations} across {len(self.images)} images")
        return total_saved

    def get_summary(self):
        logger.info(f"Generating summary statistics...")
        if not self.images:
            self.download_images()
        summary = {
            'total_images': len(self.image_data_list),
            'successful_downloads': sum(1 for _, img in self.images if img is not None),
            'failed_downloads': sum(1 for _, img in self.images if img is None),
            'images': []
        }
        for img_idx, (image_data, pil_image) in enumerate(self.images):
            summary['images'].append({
                'index': img_idx+1,
                'downloaded': pil_image is not None,
                'width': image_data['info']['width'],
                'height': image_data['info']['height'],
                'total_annotations': len(image_data['annotations']),
                'visible_annotations': len([ann for ann in image_data['annotations'] if ann.get('visible', True)])
            })
        logger.info(f"Summary generated: {summary['total_images']} images")
        return summary