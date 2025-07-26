def main(file_path: str):
    import pytest
    import sys
    from utils import file_loader  # Ensure the module is imported for pytest to discover
    import text_extraction  as te # Ensure the module is imported for pytest to discover
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
        
if __name__ == "__main__":
    
    file_path = "tests/files/AI_Risk_Management_NIST_AI_100_1.pdf"
    main(file_path)