#from image import Image
from typing import List, Dict, BinaryIO, Iterator, Set
from collections import Counter
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdftypes import PDFException
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LTTextContainer, LTPage

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

def get_text_from_page(page_number: int) -> str:
    """
    Returns the text content of the specified page.
    """
    return ""
def get_text_blocks_with_metadata(page_number: int) -> List[Dict]:
    """
    Returns text blocks with metadata from the specified page.
    """
    return []

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

def get_text_between_y_coordinates(page_number: int, start_y: float, end_y: float) -> str:
    """
    Returns text content between specified Y coordinates on the page.
    Useful for extracting sections of text that are visually grouped.
    """
    return ""
def get_text_following_header(page_number: int, header_bbox: List[float]) -> str:
    """
    Returns text content that follows a specified header bounding box.
    Useful for extracting the section content immediately after a header.
    """
    return ""
########################################################################
#Table Parsing Tools
########################################################################
def detect_tables_on_page(page_number: int) -> List[Dict]:
    """
    Detects tables on the specified page.
    Uses rules (or even a simple CV model) to find the bounding boxes of potential tables. Returns [{bbox: [...], confidence: 0.9}].
    Returns a list of dictionaries with table metadata.
    """
    return []
def extract_text_in_bbox(page_number: int, bbox: List[float]) -> str:
    """
    Extracts text content within a specified bounding box on the page.
    Useful for extracting text from detected tables or other regions.
    """
    return ""
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