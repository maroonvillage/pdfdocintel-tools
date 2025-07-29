def main(file_path: str):
    import pytest
    import sys
    from utils import file_loader  # Ensure the module is imported for pytest to discover
    import text_extraction  as te # Ensure the module is imported for pytest to discover
    
    # For visualization, we need additional libraries:
    # pip install PyMuPDF pillow
    import fitz  # PyMuPDF
    from PIL import Image, ImageDraw
    
    
    # Add the current directory to the system path
    sys.path.append(".")

    # Run the tests
    #pytest.main(["-v", "tests/test_file_loader.py"])
    
    file_stream = file_loader.open_file_from_path_or_s3(file_path, use_cache=True)
    toc_list = te.extract_toc(file_stream)
    for toc in toc_list:
        print(toc)
    
    print("Calculating total page count...")
    total_pages = te.get_total_page_count(file_stream)
    print(f"Total pages in document: {total_pages}")
    
    file_stream.seek(0)  # Reset stream position after reading TOC
    
    keyword_page_list = te.find_pages_with_keyword("Transparency", file_stream)
    print(f"Pages with 'Transparency': {keyword_page_list}")    
    
    file_stream.seek(0)  # Reset stream position after reading keyword pages
    
    headers_footer_dict = te.find_headers_and_footers(file_stream)
    print("Extracted Headers and Footers:")
    print(headers_footer_dict['headers'])
    #for page_num, header_footer in headers_footer_dict.items():
    #    print(f"Page {page_num}: Header: {header_footer['header']}, Footer: {header_footer['footer']}")
    
    file_stream.seek(0)
    target_page = 5  # Example page number to extract text from
    page_text = te.get_text_from_page(file_stream, target_page)
            
    if not page_text:
        print("No text found on this page.")
    else:
        print("--- Extracted Text ---")
        print(page_text)
        print("----------------------")
    
    file_stream.seek(0)
    # Let's imagine we know the main content of our page is between these y-coords.
    # On a standard 8.5x11 inch page (792 points high), this might be:
    # A 1-inch top margin (72 points) -> upper_y = 792 - 72 = 720
    # A 1-inch bottom margin (72 points) -> lower_y = 72
    upper_y_boundary = 720
    lower_y_boundary = 72
    print(f"--- Extracting text from page {target_page} between Y={lower_y_boundary} and Y={upper_y_boundary} ---\n")
    main_content = te.get_text_between_y_coordinates(
                file_stream,
                target_page,
                start_y=upper_y_boundary,
                end_y=lower_y_boundary
            )
    if not main_content:
        print("No text found in the specified region.")
    else:
        print("--- Extracted Content ---")
        print(main_content)
        print("-------------------------")
    
    file_stream.seek(0) # Reset stream
    target_page = 6
    all_page_blocks = te.extract_text_blocks_with_metadata(file_stream, target_page)
    
     # The text of the header we are looking for
    header_to_find = "Executive Summary" 
    
    target_header_bbox = None
    for block in all_page_blocks:
        if header_to_find.lower() in block['text'].lower():
            target_header_bbox = block['bbox']
            print(f"Found header '{header_to_find}' with bbox: {target_header_bbox}")
            break
    
    if target_header_bbox:
        # Now, call the function we just built
        file_stream.seek(0) # Reset stream again for the main function call
        section_content = te.get_text_following_header(file_stream, target_page, target_header_bbox)
        
        print("\n--- Extracted Section Content ---")
        print(section_content)
        print("---------------------------------")
    else:
        print(f"Could not find the header '{header_to_find}' on page {target_page}.")


    file_stream.seek(0) # Reset stream
    print(f"--- Extracting text blocks with metadata from page {target_page} of '{file_path}' ---\n")
    blocks = te.extract_text_blocks_with_metadata(file_stream, target_page)
    
    if not blocks:
        print("No text blocks found on this page.")
    else:
        # Sort blocks from top to bottom of the page for readability
        blocks.sort(key=lambda b: -b['bbox'][1])

        for i, block in enumerate(blocks):
            print(f"--- Block {i+1} ---")
            print(f"  Font: {block['font_name']}, Avg Size: {block['font_size']}")
            print(f"  BBox: {block['bbox']}")
            print(f"  Text: '{block['text']}'")
            print("-" * (len(str(i+1)) + 12)) # Dynamic separator
    
    
        target_page = 27
        file_stream.seek(0)  # Reset stream for table detection
        print(f"--- Detecting tables on page {target_page} of '{file_path}' ---\n")
            
        tables = te.detect_tables_on_page(file_stream, target_page)
        
        if not tables:
            print("No tables detected on this page.")
        else:
            print(f"Found {len(tables)} potential table(s):")
            for i, table in enumerate(tables):
                print(f"  Table {i+1}: BBox={table['bbox']}, Confidence={table['confidence']}")

            # --- Visualization ---
            print("\n--- Generating visualization: detected_tables.png ---")
            doc = fitz.open(file_path)
            page = doc.load_page(target_page - 1)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            draw = ImageDraw.Draw(img)

            for table in tables:
                draw.rectangle(table['bbox'], outline="red", width=2)
            
            img.save("detected_tables.png")
            print("Visualization saved.")
                
                               
if __name__ == "__main__":
    
    file_path = "tests/files/AI_Risk_Management_NIST_AI_100_1.pdf"
    main(file_path)