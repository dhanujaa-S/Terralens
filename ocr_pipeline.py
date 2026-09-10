import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps
import fitz
import io
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

LANG_MAP = {
    "english":  "eng",
    "hindi":    "hin",
    "tamil":    "tam",
    "telugu":   "tel",
    "kannada":  "kan",
    "bengali":  "ben",
    "gujarati": "guj",
    "marathi":  "mar",
    "auto":     "eng+hin+tam+tel+kan",
}

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
CONFIDENCE_FALLBACK_THRESHOLD = 0.5


@dataclass
class OCRResult:
    """
    Returned by OCRPipeline.process_file().
    Contains extracted text, confidence scores, and the preprocessed image
    for display in the Streamlit UI.
    """
    raw_text: str
    language_detected: str
    confidence: float
    page_count: int
    method_used: str
    image_quality_score: float
    preprocessed_image: Optional[np.ndarray] = None


class ImagePreprocessor:
    """
    Cleans scanned land record images using OpenCV.
    All private methods take and return numpy arrays (grayscale after step 1).
    """

    MAX_DESKEW_ANGLE = 15.0

    def preprocess(self, image: np.ndarray) -> tuple:
        """
        Run full preprocessing pipeline.
        Returns (cleaned_image, quality_score).
        quality_score is Laplacian variance normalized to 0.0-1.0.
        """
        quality_before = self._quality_score(image)
        img = self._to_grayscale(image)
        img = self._deskew(img)
        img = self._remove_noise(img)
        img = self._enhance_contrast(img)
        img = self._binarize(img)
        img = self._remove_borders(img)
        quality_after = self._quality_score(img)
        logger.info(f"Image quality: {quality_before:.2f} -> {quality_after:.2f}")
        return img, quality_after

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        """Convert a BGR image to grayscale; pass through if already single-channel."""
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _deskew(self, img: np.ndarray) -> np.ndarray:
        """Detect and correct small rotational skew in a scanned document image."""
        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # minAreaRect on raw per-pixel text glyphs produces wildly unstable
        # angles because a page of text is a scattered pixel cloud, not a
        # single rotated shape. Dilating merges characters into line/block
        # blobs so the bounding rectangle reflects the page's true
        # orientation instead of noise from individual glyph shapes.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        dilated = cv2.dilate(binary, kernel, iterations=2)

        coords = np.column_stack(np.where(dilated > 0))
        if len(coords) == 0:
            return img

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle

        if abs(angle) < 0.5:
            return img

        if abs(angle) > self.MAX_DESKEW_ANGLE:
            logger.warning(
                f"Deskew angle {angle:.2f} degrees exceeds the safe threshold "
                f"({self.MAX_DESKEW_ANGLE}) — treating as an unreliable estimate "
                f"and leaving the image orientation unchanged."
            )
            return img

        h, w = img.shape
        centre = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(centre, -angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        logger.info(f"Deskew angle corrected: {angle:.2f} degrees")
        return rotated

    def _remove_noise(self, img: np.ndarray) -> np.ndarray:
        """Remove speckle noise via median blur followed by morphological opening."""
        denoised = cv2.medianBlur(img, 3)
        kernel = np.ones((2, 2), np.uint8)
        return cv2.morphologyEx(denoised, cv2.MORPH_OPEN, kernel)

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """Enhance local contrast using CLAHE."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(img)

    def _binarize(self, img: np.ndarray) -> np.ndarray:
        """Convert grayscale image to a clean binary image via adaptive thresholding."""
        return cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
            blockSize=11, C=2,
        )

    def _remove_borders(self, img: np.ndarray) -> np.ndarray:
        """Crop the image down to the largest content contour, with a small margin."""
        _, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        margin = 10
        img_h, img_w = img.shape[:2]
        x0 = max(0, x - margin)
        y0 = max(0, y - margin)
        x1 = min(img_w, x + w + margin)
        y1 = min(img_h, y + h + margin)

        return img[y0:y1, x0:x1]

    def _quality_score(self, img: np.ndarray) -> float:
        """Compute an image sharpness score via normalized Laplacian variance."""
        gray = self._to_grayscale(img) if len(img.shape) == 3 else img
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        return float(min(1.0, variance / 1000.0))


class PDFConverter:
    """
    Converts PDF files to a list of numpy images using PyMuPDF.
    Each page becomes one numpy array at 300 DPI for best OCR quality.
    """

    def convert(self, pdf_bytes: bytes, dpi: int = 300) -> list:
        """
        Convert all pages of a PDF to numpy images.
        Returns list of numpy arrays, one per page.
        Raises ValueError if pdf_bytes is not a valid PDF.
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Invalid PDF file: {e}")

        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            images.append(img)
            logger.info(f"PDF page {page_num + 1}/{len(doc)} converted")
        doc.close()
        return images


class TesseractOCR:
    """
    Primary OCR engine using Google Tesseract.
    Supports 8 Indian languages plus English.
    Returns per-word average confidence alongside extracted text.
    """

    def __init__(self, tesseract_path: Optional[str] = None):
        """
        Initialize Tesseract. If tesseract_path given, set the binary path.
        Logs a warning if Tesseract is not installed.
        """
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        try:
            pytesseract.get_tesseract_version()
            logger.info("Tesseract initialized successfully.")
        except Exception as e:
            logger.warning(
                f"Tesseract not found: {e}. "
                "Install with: sudo apt install tesseract-ocr tesseract-ocr-hin"
            )

    def extract(self, img: np.ndarray, language: str = "auto") -> tuple:
        """
        Extract text from a preprocessed grayscale image.
        Returns (text, confidence) where confidence is 0.0-1.0.
        Returns ("", 0.0) on any error.
        """
        lang_code = LANG_MAP.get(language.lower(), "eng+hin")
        config = "--oem 3 --psm 6"
        pil_img = Image.fromarray(img)
        try:
            data = pytesseract.image_to_data(
                pil_img,
                lang=lang_code,
                config=config,
                output_type=pytesseract.Output.DICT,
            )
            text = pytesseract.image_to_string(pil_img, lang=lang_code, config=config)
            confs = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
            return text.strip(), round(avg_conf, 3)
        except Exception as e:
            logger.error(f"Tesseract extraction error: {e}")
            return "", 0.0


class EasyOCRFallback:
    """
    Fallback OCR engine using EasyOCR.
    Only loaded into memory when Tesseract confidence is below threshold.
    Lazy loading prevents unnecessary memory use on every startup.
    """

    def __init__(self):
        """Do NOT import easyocr here. Set reader to None for lazy loading."""
        self._reader = None

    def _load(self) -> None:
        """
        Lazy-load EasyOCR reader on first use.
        Only called when Tesseract confidence falls below threshold.
        """
        if self._reader is None:
            try:
                import easyocr
                self._reader = easyocr.Reader(["en", "hi"], gpu=False)
                logger.info("EasyOCR reader loaded successfully.")
            except ImportError:
                logger.warning("EasyOCR not installed. Run: pip install easyocr")
            except Exception as e:
                logger.error(f"EasyOCR load error: {e}")

    def extract(self, img: np.ndarray) -> tuple:
        """
        Extract text using EasyOCR.
        Returns (text, confidence) where confidence is 0.0-1.0.
        Returns ("", 0.0) on any error or if EasyOCR is not available.
        """
        self._load()
        if self._reader is None:
            return "", 0.0
        try:
            results = self._reader.readtext(img)
            texts = [text for (_, text, _) in results]
            confs = [conf for (_, _, conf) in results]
            full_text = " ".join(texts)
            avg_conf = round(sum(confs) / len(confs), 3) if confs else 0.0
            return full_text, avg_conf
        except Exception as e:
            logger.error(f"EasyOCR extraction error: {e}")
            return "", 0.0


class OCRPipeline:
    """
    End-to-end OCR pipeline for Terra Lens.
    Accepts PDF or image bytes, preprocesses, runs Tesseract,
    falls back to EasyOCR if confidence is low, returns OCRResult.
    This is the ONLY class imported by other modules.
    Usage: result = OCRPipeline().process_file(file_bytes, filename, language)
    """

    def __init__(self, tesseract_path: Optional[str] = None):
        """Initialize all sub-components of the OCR pipeline."""
        self.preprocessor = ImagePreprocessor()
        self.pdf_converter = PDFConverter()
        self.tesseract = TesseractOCR(tesseract_path)
        self.easyocr = EasyOCRFallback()

    def _decode_image_with_exif(self, file_bytes: bytes) -> Optional[np.ndarray]:
        """
        Decode image bytes to a BGR numpy array, applying any EXIF orientation
        tag first so photographed documents (e.g. from a phone camera) are
        upright before preprocessing. cv2.imdecode ignores EXIF orientation,
        which otherwise leaves a correctly-taken photo rotated ~90/180/270
        degrees. Falls back to plain cv2 decoding if PIL/EXIF handling fails.
        """
        try:
            pil_img = Image.open(io.BytesIO(file_bytes))
            pil_img = ImageOps.exif_transpose(pil_img)
            pil_img = pil_img.convert("RGB")
            rgb_array = np.array(pil_img)
            return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.warning(f"EXIF-aware decode failed, falling back to cv2.imdecode: {e}")
            nparr = np.frombuffer(file_bytes, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def process_file(
        self,
        file_bytes: bytes,
        filename: str,
        language: str = "auto",
    ) -> OCRResult:
        """
        Main entry point.
        Accepts PDF or image bytes plus the original filename (used to detect type).
        Returns a fully populated OCRResult.
        Raises ValueError for unsupported file types.
        """
        ext = Path(filename).suffix.lower()

        if ext == ".pdf":
            try:
                images = self.pdf_converter.convert(file_bytes)
            except Exception as e:
                logger.error(f"PDF conversion failed: {e}")
                images = []
        elif ext in SUPPORTED_IMAGE_EXTENSIONS:
            img = self._decode_image_with_exif(file_bytes)
            if img is None:
                logger.error(f"Could not decode image: {filename}")
                images = []
            else:
                images = [img]
        else:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: .pdf, {', '.join(SUPPORTED_IMAGE_EXTENSIONS)}"
            )

        if not images:
            return OCRResult(
                raw_text="",
                language_detected=language,
                confidence=0.0,
                page_count=0,
                method_used="none",
                image_quality_score=0.0,
            )

        all_text_parts = []
        all_confs = []
        method_used = "tesseract"
        last_preprocessed = None
        last_quality = 0.0

        for page_idx, raw_img in enumerate(images):
            logger.info(f"Processing page {page_idx + 1}/{len(images)}")

            clean_img, quality = self.preprocessor.preprocess(raw_img)
            last_preprocessed = clean_img
            last_quality = quality

            text, conf = self.tesseract.extract(clean_img, language)
            logger.info(f"Tesseract confidence: {conf:.2f}")

            if conf < CONFIDENCE_FALLBACK_THRESHOLD:
                logger.info(
                    f"Confidence {conf:.2f} below threshold "
                    f"{CONFIDENCE_FALLBACK_THRESHOLD}. Trying EasyOCR..."
                )
                easy_text, easy_conf = self.easyocr.extract(clean_img)
                if easy_conf > conf:
                    text, conf = easy_text, easy_conf
                    method_used = "easyocr"
                    logger.info(f"EasyOCR used. Confidence: {easy_conf:.2f}")

            all_text_parts.append(text)
            all_confs.append(conf)

        final_text = "\n\n--- PAGE BREAK ---\n\n".join(all_text_parts)
        avg_confidence = round(sum(all_confs) / len(all_confs), 3)
        logger.info(
            f"OCR complete. Pages: {len(images)}, "
            f"Method: {method_used}, "
            f"Avg confidence: {avg_confidence:.2f}"
        )

        return OCRResult(
            raw_text=final_text,
            language_detected=language,
            confidence=avg_confidence,
            page_count=len(images),
            method_used=method_used,
            image_quality_score=round(last_quality, 3),
            preprocessed_image=last_preprocessed,
        )


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python modules/ocr_pipeline.py <path_to_file>")
        print("Example: python modules/ocr_pipeline.py sample.pdf")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path, "rb") as f:
        data = f.read()

    pipeline = OCRPipeline()
    result = pipeline.process_file(data, path.name, language="auto")

    print("\n" + "=" * 60)
    print(f"File:           {path.name}")
    print(f"Pages:          {result.page_count}")
    print(f"Method:         {result.method_used}")
    print(f"OCR Confidence: {result.confidence * 100:.1f}%")
    print(f"Image Quality:  {result.image_quality_score * 100:.1f}%")
    print(f"Text length:    {len(result.raw_text)} chars")
    print("=" * 60)
    print(result.raw_text[:3000])
    print("\nModule 1 — ocr_pipeline.py OK")
