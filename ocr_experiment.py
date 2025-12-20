import layoutparser as lp
from pdf2image import convert_from_path
import numpy as np
import cv2

from layoutparser.models import PaddleDetectionLayoutModel
model = PaddleDetectionLayoutModel(
    'lp://PubLayNet/ppyolov2_r50vd_dcn_365e/config',
    label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
)

import fitz
file_path = "./data/form_scanned.pdf"
dpi = 300  # choose desired dpi here
zoom = dpi / 72  # zoom factor, standard: 72 dpi
magnify = fitz.Matrix(zoom, zoom)  # magnifies in x, resp. y direction
doc = fitz.open(file_path)  # open document
for page in doc:
    pix = page.get_pixmap(matrix=magnify)  # render page to an image
    pix.save(f"page-{page.number}.png")


img = cv2.imread("./page-0.png")
# 2. Load a pre-trained model (e.g., for academic papers)

ocr_agent = lp.TesseractAgent.with_tesseract_executable(
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    languages='eng'
)


# 3. Process a page
# Convert PIL image to numpy array for Layout-Parser
layout = ocr_agent.detect(img)
    # collect all the layout elements of the `WORD` level

model = lp.AutoLayoutModel(
    'lp://PubLayNet/ppyolov2_r50vd_dcn_365e/config',
    label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
)

# 2. Detect layout
layout = model.detect(img)

# 3. Filter for just "Text" or "Title" blocks
text_blocks = lp.Layout([b for b in layout if b.type in ["Text", "Title"]])
