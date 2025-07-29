#from image import Image
from typing import List, Dict, BinaryIO, Iterator, Set, Tuple
from collections import Counter
import math
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdftypes import PDFException
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LTTextContainer, LTPage, LTTextLine, LTTextBoxHorizontal, LTChar, LTRect, LTLine

########################################################################
#Document Navigation & Inspection Tools
########################################################################
def get_total_page_count(file_stream: BinaryIO) -> int: 
    """
    Returns the total number of pages in the document.
    """
    try:
        #start_page = 0
        parser = PDFParser(file_stream)
        pdf_document = PDFDocument(parser)
        # Attempt graceful handling of incorrect pages
        total_pages = 0
        try:
            total_pages = len(list(PDFPage.create_pages(pdf_document)))
        except Exception as ex:
            print("Could not get all pages, document malformed.")
                        
        #page_numbers = set(range(start_page, min(total_pages,500))) # Limit to the first 500 pages
    except FileNotFoundError as e:
        print(f"get_total_page_count - {e}")
        raise
    except AttributeError as e:
        print(f"AttributeError in get_total_page_count - {e}")
        raise
    except Exception as e:
        print(f"An error occurred during JSON conversion: {e}")
        raise
                
    return total_pages

def get_text_from_page(
    file_stream: BinaryIO,
    page_number: int
) -> str:
    """
    Returns the text content of the specified page, preserving paragraph
    structure and reading order.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        page_number (int): The 1-based page number to extract text from.

    Returns:
        A single string containing the page's text, with paragraphs
        separated by double newlines. Returns an empty string if the page
        is not found or contains no text.
    """
    # Standard pdfminer setup
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

    # Get the specific page object from the document
    # The pagenos parameter uses 0-based indexing
    target_pages = {page_number - 1}
    page = next(PDFPage.get_pages(file_stream, pagenos=target_pages, check_extractable=False), None)

    if not page:
        print(f"Warning: Page {page_number} not found in document.")
        return ""

    # Process the page layout
    interpreter.process_page(page)
    layout = device.get_result()

    # Extract text blocks (LTTextBoxHorizontal) from the layout
    text_blocks = [
        element for element in layout if isinstance(element, LTTextBoxHorizontal)
    ]
    
    # Sort the text blocks by their vertical position (top-to-bottom)
    # The y-coordinate origin is at the bottom, so we sort by -y1 (descending)
    text_blocks.sort(key=lambda b: -b.y1)
    
    # Join the text from each block, separating them with double newlines
    # to maintain paragraph separation.
    return "\n\n".join([block.get_text().strip() for block in text_blocks])

def extract_text_blocks_with_metadata(
    file_stream: BinaryIO,
    page_number: int # 1-based page number
) -> List[Dict]:
    """
    Extracts all text blocks from a specified page, along with rich metadata
    for each block.

    A text block is represented by pdfminer's LTTextBoxHorizontal.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        page_number (int): The 1-based page number to extract from.

    Returns:
        A list of dictionaries. Each dictionary represents a text block and
        contains the following keys:
        - 'text' (str): The text content of the block.
        - 'page_number' (int): The page number it was found on.
        - 'font_name' (str): The most common font name in the block.
        - 'font_size' (float): The average font size in the block.
        - 'bbox' (tuple): The bounding box (x0, y0, x1, y1) of the block.
        - 'width' (float): The width of the text block.
        - 'height' (float): The height of the text block.
    """
    # Basic pdfminer setup
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

    # Get the specific page, pagenos is 0-indexed
    target_pages = {page_number - 1}
    page_to_process = next(PDFPage.get_pages(file_stream, pagenos=target_pages, check_extractable=False), None)

    if not page_to_process:
        print(f"Warning: Page {page_number} not found in document.")
        return []

    interpreter.process_page(page_to_process)
    layout = device.get_result()

    text_blocks = []

    for element in layout:
        # We are only interested in text boxes
        if isinstance(element, LTTextBoxHorizontal):
            # --- Metadata Extraction ---
            
            # 1. Text content and basic geometry
            text = element.get_text()
            bbox = element.bbox
            
            # 2. Font analysis (more complex)
            # We iterate down to the character level to get font info
            font_names = []
            font_sizes = []
            for text_line in element:
                if isinstance(text_line, LTTextLine):
                    for character in text_line:
                        if isinstance(character, LTChar):
                            font_names.append(character.fontname)
                            font_sizes.append(character.size)
            
            # Calculate the most common font name and average size
            most_common_font = None
            avg_font_size = 0.0
            if font_names:
                most_common_font = Counter(font_names).most_common(1)[0][0]
            if font_sizes:
                avg_font_size = round(sum(font_sizes) / len(font_sizes), 2)

            block_data = {
                "text": text.strip(),
                "page_number": page_number,
                "font_name": most_common_font,
                "font_size": avg_font_size,
                "bbox": bbox,
                "width": element.width,
                "height": element.height,
            }
            text_blocks.append(block_data)

    return text_blocks

# def get_page_image(page_number: int, dpi: int = 150) -> Image:
#     """
#     Returns an image of the specified page at the given DPI.
#     """
#     return Image.new('RGB', (100, 100), color = 'white')
########################################################################
#Table of Contents Specific Tools
########################################################################
def _iter_layout_elements(layout: LTPage) -> Iterator[LTTextContainer]:
    """
    A recursive generator to iterate through all text-containing elements
    in a PDF page layout.
    """
    for element in layout:
        if isinstance(element, LTTextContainer):
            yield element
        # If the element is a container, recurse into it
        elif hasattr(element, '_objs'):
            yield from _iter_layout_elements(element)
            
def extract_toc(file_stream: BinaryIO) -> List[Dict]:
    """
    Extracts the Table of Contents from the document.
    Returns a list of dictionaries with TOC entries.
    """
    toc_list = []
    parser = PDFParser(file_stream)
    document = PDFDocument(parser)
    # Get pages 
    # Pre-build a map from page ID to page number (1-based index)
    # This is much more efficient than searching for the page each time.
    all_pages = list(PDFPage.create_pages(document))
    pageid_to_num = {page.pageid: i + 1 for i, page in enumerate(all_pages)}
            
    outlines = document.get_outlines()
    for (level, title, dest, action, se) in outlines:
        
        page_info = '[Container]' # Default for non-linking entries
        if dest:
            try:
                # resolve_dest returns a tuple like (page_id, spec, arg1, arg2, ...)
                # The first element is the page object's ID we need.
                page_id = document.resolve_dest(dest)[0]
                        
                # Look up the page number from our pre-built map
                if page_id in pageid_to_num:
                    page_info = pageid_to_num[page_id]
                            
            except (PDFException, IndexError) as e:
                # Some destinations might not resolve correctly or might be invalid
                print(f"Warning: Could not resolve destination for '{title}'. Error: {e}")
                page_info = "[Unresolved Destination]" # Or None, or however you want to handle it
        elif action:
            # If there's an action, check if it's a URI
            # action is a dictionary, e.g., {'S': /'URI', 'URI': b'http://example.com'}
            if isinstance(action, dict):
                action_type = action.get('S')
                if action_type and action_type.name == 'URI':
                    uri = action.get('URI')
                    # URI can be bytes, so decode it
                    page_info = f"URI: {uri.decode('utf-8') if isinstance(uri, bytes) else uri}"
                else:
                    page_info = f"[Action: {action_type.name if hasattr(action_type, 'name') else 'Unknown'}]"
            else:
                page_info = '[Unknown Action]'
                                        
        toc_list.append({"level": level, "title": title, "page": page_info})  
                          
    return toc_list

def find_pages_with_keyword(
    keyword: str,
    file_stream: BinaryIO,
    start_page: int = 1,
    end_page: int = None,
    case_sensitive: bool = False
) -> List[int]:
    """
    Finds pages containing a specified keyword in a PDF.

    This version is more robust, efficient, and has a clearer API.

    Args:
        keyword (str): The keyword to search for.
        file_stream (BinaryIO): The binary file stream of the PDF.
        start_page (int): The 1-based page number to start searching from. Defaults to 1.
        end_page (int): The 1-based page number to end searching at (inclusive). 
                          Defaults to the end of the document.
        case_sensitive (bool): Whether the search should be case-sensitive.

    Returns:
        List[int]: A sorted list of 1-based page numbers where the keyword was found.
    """
    found_pages: Set[int] = set()
    
    # Prepare the keyword for searching to avoid repeated processing in the loop
    search_keyword = keyword if case_sensitive else keyword.lower()
    
    # Setup pdfminer resources
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

     # Use enumerate to get a reliable 0-based page index
    for i, page in enumerate(PDFPage.get_pages(file_stream, check_extractable=False)):
        current_page_num_0_indexed = i
        
        # --- THIS IS THE FIX ---
        # Filter pages based on the start_page and end_page parameters
        if current_page_num_0_indexed < start_page - 1:
            continue
        if end_page is not None and current_page_num_0_indexed >= end_page:
            break # We've passed the desired page range, so we can stop

        interpreter.process_page(page)
        layout = device.get_result()
        
        # Use the recursive iterator to find all text elements
        for element in _iter_layout_elements(layout):
            text = element.get_text()
            element_text = text if case_sensitive else text.lower()
            
            if search_keyword in element_text:
                # Add the 1-based page number to our set
                found_pages.add(current_page_num_0_indexed + 1)
                # Found it on this page, no need to check other elements
                break 

    return sorted(list(found_pages))

def identify_toc_candidate_lines(page_number: int) -> List[Dict]:
    """
    Identifies candidate lines for the Table of Contents on the specified page.
    Returns a list of dictionaries with line metadata.
    """
    return []
def parse_toc_line(line_text: str) -> Dict:
    """
    Parses a line of text to identify TOC structure.
    Takes a single line (e.g., "Chapter 1: Introduction ........ 5") and returns {title: "Chapter 1: Introduction", page_label: "5"}
    Returns a dictionary with parsed TOC information.
    """
    return {"text": line_text, "level": 0, "page": 0}
def get_indentation_level(text_block: Dict) -> int:
    """
    Determines hierarchy in the ToC by analyzing the x0 coordinate from the block's bounding box.
    Returns an integer representing the level.
    """
    return 0
########################################################################
#Section/Chapter Parsing Tools
########################################################################
def find_potential_headers(page_number: int) -> List[Dict]: 
    """
    Identifies text blocks that are likely headers based on font size, boldness, and spacing.
    Returns a list of dictionaries with potential header metadata.
    """
    return []

def find_headers_and_footers(
    file_stream: BinaryIO,
    scan_pages: int = 10,
    top_margin: float = 0.90,
    bottom_margin: float = 0.10,
    min_occurrence: int = 3
) -> dict:
    """
    Analyzes the first few pages of a PDF to identify common headers and footers.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        scan_pages (int): The number of pages to scan to find patterns.
        top_margin (float): The vertical threshold for the header (e.g., 0.90 means top 10%).
        bottom_margin (float): The vertical threshold for the footer (e.g., 0.10 means bottom 10%).
        min_occurrence (int): The minimum number of times text must appear to be considered.

    Returns:
        dict: A dictionary with 'headers' and 'footers' keys, containing lists
              of common text elements found.
    """
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)
    
    potential_elements = Counter()
    
    # Use enumerate to get a page index for the scan limit
    for i, page in enumerate(PDFPage.get_pages(file_stream, check_extractable=False)):
        if i >= scan_pages:
            break
            
        page_height = page.mediabox[3] # [x0, y0, x1, y1]
        header_y_threshold = page_height * top_margin
        footer_y_threshold = page_height * bottom_margin
        
        interpreter.process_page(page)
        layout = device.get_result()
        
        for element in _iter_layout_elements(layout):
            text = element.get_text().strip()
            if not text:
                continue

            # Check if element is in header or footer zone
            if element.y1 > header_y_threshold or element.y0 < footer_y_threshold:
                # Use a simplified, rounded position for grouping
                y_pos_bucket = round(element.y0 / 10) * 10
                potential_elements[(text, y_pos_bucket)] += 1
                
    # Filter for elements that occurred frequently
    result = {"headers": [], "footers": []}
    
    # Re-get the height of the first page for classification
    file_stream.seek(0)
    first_page = next(PDFPage.get_pages(file_stream))
    page_height = first_page.mediabox[3]
    footer_y_threshold = page_height * bottom_margin

    for (text, y_pos), count in potential_elements.items():
        if count >= min_occurrence:
            if y_pos > footer_y_threshold:
                result["headers"].append(text)
            else:
                result["footers"].append(text)
                
    return result

def get_text_between_y_coordinates(
    file_stream: BinaryIO,
    page_number: int,
    start_y: float,
    end_y: float
) -> str:
    """
    Returns text content between specified Y coordinates on a page.

    The Y-coordinate system in pdfminer has its origin (0) at the bottom
    of the page. This function correctly handles if start_y and end_y
    are provided in ascending or descending order.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        page_number (int): The 1-based page number to extract from.
        start_y (float): One of the vertical boundary coordinates.
        end_y (float): The other vertical boundary coordinate.

    Returns:
        A single string containing the content found in the specified
        vertical slice, with elements sorted top-to-bottom.
    """
    # Standard pdfminer setup
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

    # Get the specific page
    target_pages = {page_number - 1}
    page = next(PDFPage.get_pages(file_stream, pagenos=target_pages, check_extractable=False), None)

    if not page:
        print(f"Warning: Page {page_number} not found in document.")
        return ""

    interpreter.process_page(page)
    layout = device.get_result()
    
    # Determine the upper and lower bounds of our selection area
    upper_bound = max(start_y, end_y)
    lower_bound = min(start_y, end_y)

    found_elements = []
    for element in _iter_layout_elements(layout):
        # An element's bounding box is (x0, y0, x1, y1)
        element_bottom = element.y0
        element_top = element.y1
        
        # Check for vertical overlap. The element is in the slice if it's
        # not entirely above the upper bound or entirely below the lower bound.
        if not (element_bottom > upper_bound or element_top < lower_bound):
            found_elements.append(element)
    
    # Sort the found elements from top to bottom for correct reading order
    found_elements.sort(key=lambda el: -el.y1)
    
    # Join the text of the found elements
    return "\n".join([el.get_text().strip() for el in found_elements])

def _bboxes_are_close(bbox1: Tuple[float, ...], bbox2: Tuple[float, ...], tolerance: float = 1.0) -> bool:
    """Checks if two bounding boxes are almost identical."""
    return all(abs(c1 - c2) < tolerance for c1, c2 in zip(bbox1, bbox2))

def get_text_following_header(
    file_stream: BinaryIO,
    page_number: int,
    header_bbox: List[float]
) -> str:
    """
    Returns text content that follows a specified header bounding box until
    the next header of the same or greater importance is found.

    This is useful for extracting the content of a specific section.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        page_number (int): The 1-based page number where the header is located.
        header_bbox (List[float]): The bounding box (x0, y0, x1, y1) of the header.

    Returns:
        A single string containing the content of the section, with paragraphs
        separated by double newlines. Returns an empty string if the header
        is not found or has no content following it.
    """
    # This part is a simplified version of `extract_text_blocks_with_metadata`
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

    target_pages = {page_number - 1}
    page = next(PDFPage.get_pages(file_stream, pagenos=target_pages, check_extractable=False), None)

    if not page:
        return ""

    interpreter.process_page(page)
    layout = device.get_result()

    # 1. Get all text blocks with metadata
    all_blocks = []
    for element in layout:
        if isinstance(element, LTTextBoxHorizontal):
            font_sizes = [char.size for line in element if isinstance(line, LTTextLine) for char in line if isinstance(char, LTChar)]
            avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0
            all_blocks.append({
                "text": element.get_text(),
                "bbox": element.bbox,
                "font_size": avg_font_size
            })

    # Sort all blocks top-to-bottom
    all_blocks.sort(key=lambda b: -b['bbox'][1])
    
    # 2. Find the header block and its properties
    header_index = -1
    header_font_size = 0
    for i, block in enumerate(all_blocks):
        if _bboxes_are_close(block['bbox'], header_bbox):
            header_index = i
            header_font_size = block['font_size']
            break

    if header_index == -1:
        # Header with the specified bbox was not found on this page
        return ""

    # 3. Collect content blocks that follow the header
    content_blocks = []
    # Start searching from the element right after the header
    for i in range(header_index + 1, len(all_blocks)):
        current_block = all_blocks[i]
        
        # 4. Stop if we find a new header
        # Heuristic: A new header has a font size equal to or larger than our
        # reference header. This captures sibling headers (H2 -> H2) and
        # parent-level headers (H3 -> H2).
        if current_block['font_size'] >= header_font_size:
            break
        
        # Otherwise, it's part of the section's content
        content_blocks.append(current_block['text'].strip())

    # 5. Join the collected text for a clean output
    return "\n\n".join(content_blocks)


########################################################################
#Table Parsing Tools
########################################################################
# Helper function to check if a smaller bbox is inside a larger one
def _is_inside(inner_bbox, outer_bbox):
    ix0, iy0, ix1, iy1 = inner_bbox
    ox0, oy0, ox1, oy1 = outer_bbox
    return ox0 <= ix0 and oy0 <= iy0 and ox1 >= ix1 and oy1 >= iy1

# Helper function to merge overlapping bounding boxes
def _merge_overlapping_bboxes(bboxes: List[Dict]) -> List[Dict]:
    if not bboxes:
        return []

    # Sort by confidence score, descending
    bboxes.sort(key=lambda b: -b['confidence'])
    
    merged = []
    while bboxes:
        # Pop the most confident bbox
        base = bboxes.pop(0)
        
        # Find all other bboxes that overlap significantly with the base
        base_area = (base['bbox'][2] - base['bbox'][0]) * (base['bbox'][3] - base['bbox'][1])
        to_merge_indices = []
        for i, other in enumerate(bboxes):
            # Calculate intersection area
            ix0 = max(base['bbox'][0], other['bbox'][0])
            iy0 = max(base['bbox'][1], other['bbox'][1])
            ix1 = min(base['bbox'][2], other['bbox'][2])
            iy1 = min(base['bbox'][3], other['bbox'][3])
            
            if ix1 > ix0 and iy1 > iy0: # Overlap exists
                intersection_area = (ix1 - ix0) * (iy1 - iy0)
                other_area = (other['bbox'][2] - other['bbox'][0]) * (other['bbox'][3] - other['bbox'][1])
                
                # If overlap is more than 50% of the other box's area, mark for merging
                if intersection_area / other_area > 0.5:
                    to_merge_indices.append(i)

        # Merge the bboxes
        for i in sorted(to_merge_indices, reverse=True):
            other = bboxes.pop(i)
            base['bbox'] = [
                min(base['bbox'][0], other['bbox'][0]),
                min(base['bbox'][1], other['bbox'][1]),
                max(base['bbox'][2], other['bbox'][2]),
                max(base['bbox'][3], other['bbox'][3]),
            ]
        
        merged.append(base)
        
    return merged

def detect_tables_on_page(
    file_stream: BinaryIO,
    page_number: int,
    min_table_area: float = 10000.0,
    confidence_threshold: float = 0.7
) -> List[Dict]:
    """
    Detects tables on a specified page using layout heuristics.

    This function identifies large rectangular areas that are likely to be
    tables based on the density of text boxes and lines they contain.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        page_number (int): The 1-based page number to analyze.
        min_table_area (float): The minimum area a rectangle must have to be
                                considered a potential table.
        confidence_threshold (float): The minimum confidence score for a
                                      detected region to be returned.

    Returns:
        A list of dictionaries, where each dict represents a detected table
        and contains 'bbox' and 'confidence' keys.
    """
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

    target_pages = {page_number - 1}
    page = next(PDFPage.get_pages(file_stream, pagenos=target_pages, check_extractable=False), None)
    if not page:
        return []

    interpreter.process_page(page)
    layout = device.get_result()

    # 1. Extract all relevant layout elements
    rects = [el for el in layout if isinstance(el, LTRect)]
    lines = [el for el in layout if isinstance(el, LTLine)]
    text_boxes = [el for el in layout if isinstance(el, LTTextBoxHorizontal)]

    # 2. Identify candidate table regions (large rectangles)
    potential_tables = []
    for r in rects:
        area = r.width * r.height
        if area > min_table_area:
            # 3. Score each candidate based on its contents
            score = 0
            
            # More contained text boxes are a good sign
            contained_text_boxes = [tb for tb in text_boxes if _is_inside(tb.bbox, r.bbox)]
            score += len(contained_text_boxes) * 2 # Weight text boxes highly
            
            # Contained lines are also a good sign
            contained_lines = [l for l in lines if _is_inside(l.bbox, r.bbox)]
            score += len(contained_lines) * 1

            # 4. Convert raw score to a confidence value (0-1) using a sigmoid function
            # This is a simple way to map an unbounded score to a bounded probability.
            # The parameters (k, x0) can be tuned.
            k = 0.1  # Steepness of the curve
            x0 = 30  # Midpoint (score at which confidence is 0.5)
            confidence = 1 / (1 + math.exp(-k * (score - x0)))
            
            if confidence > confidence_threshold:
                potential_tables.append({
                    "bbox": list(r.bbox),
                    "confidence": round(confidence, 3)
                })

    # 5. Merge highly overlapping detections
    merged_tables = _merge_overlapping_bboxes(potential_tables)
    
    return merged_tables


def _check_bbox_overlap(bbox1: Tuple, bbox2: Tuple) -> bool:
    """Checks if two bounding boxes overlap."""
    ax0, ay0, ax1, ay1 = bbox1
    bx0, by0, bx1, by1 = bbox2
    # True if the two boxes have a non-zero intersection area
    return not (ax1 < bx0 or ax0 > bx1 or ay1 < by0 or ay0 > by1)

def extract_text_in_bbox(
    file_stream: BinaryIO,
    page_number: int,  # 1-based page number
    bbox: Tuple[float, float, float, float]
) -> str:
    """
    Extracts text from a specified bounding box on a given page.

    Args:
        file_stream (BinaryIO): The binary file stream of the PDF.
        page_number (int): The 1-based page number to extract from.
        bbox (Tuple[float, float, float, float]): The bounding box (x0, y0, x1, y1)
                                                   to extract text from.

    Returns:
        str: A string containing all text found within the bounding box,
             sorted approximately by vertical position.
    """
    # Setup pdfminer resources
    resource_manager = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(resource_manager, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, device)

    # Get the specific page
    # Note: pagenos is 0-indexed
    target_pages = {page_number - 1}
    page_to_process = next(PDFPage.get_pages(file_stream, pagenos=target_pages, check_extractable=False), None)

    if not page_to_process:
        return ""

    interpreter.process_page(page_to_process)
    layout = device.get_result()

    found_elements = []
    for element in _iter_layout_elements(layout):
        if _check_bbox_overlap(element.bbox, bbox):
            found_elements.append(element)
            
    # Sort elements from top to bottom (higher y1 is higher on page)
    found_elements.sort(key=lambda el: -el.y1)

    return "".join(el.get_text() for el in found_elements)

def parse_text_into_table(raw_text: str, delimiter: str = ' ') -> List[List[str]]:
    """
    Parses raw text into a structured table format.
    Splits the text by the specified delimiter and returns a list of rows, where each row is a list of cell values.
    """
    return [row.split(delimiter) for row in raw_text.split('\n') if row.strip()]
def extract_table_from_bbox_as_json(page_number: int, bbox: List[float]) -> List[Dict]:
    """
    Extracts a table from the specified bounding box on the page and returns it as a list of dictionaries.
    Each dictionary represents a row in the table with column names as keys.
    """
    raw_text = extract_text_in_bbox(page_number, bbox)
    table_data = parse_text_into_table(raw_text)
    return [{"column1": row[0], "column2": row[1]} for row in table_data if len(row) >= 2]