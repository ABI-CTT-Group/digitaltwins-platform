import sys
import argparse
try:
    import pydicom
except ImportError:
    print("Error: pydicom is not installed. Please install it using 'pip install pydicom'.")
    sys.exit(1)

def print_all_tags(dataset):
    print(f"{'Tag':<20} | {'VR':<4} | {'Keyword':<30} | {'Value'}")
    print("-" * 80)
    for element in dataset:
        tag_str = str(element.tag)
        vr = element.VR
        keyword = element.keyword
        value = str(element.value)[:100]  # Truncate very long values for display
        if len(str(element.value)) > 100:
            value += "..."
        print(f"{tag_str:<20} | {vr:<4} | {keyword:<30} | {value}")

def print_single_tag(dataset, tag_identifier):
    try:
        # Try treating tag_identifier as a keyword first
        if hasattr(dataset, tag_identifier):
            element = dataset.data_element(tag_identifier)
            if element is not None:
                 print(f"{element.tag} - {element.keyword} ({element.VR}): {element.value}")
                 return

        # Try parsing as a hex group/element pair, e.g., "0010,0010"
        if "," in tag_identifier:
            group_str, elem_str = tag_identifier.split(",")
            group = int(group_str, 16)
            elem = int(elem_str, 16)
            tag = pydicom.tag.Tag(group, elem)
            
            if tag in dataset:
                element = dataset[tag]
                print(f"{element.tag} - {element.keyword} ({element.VR}): {element.value}")
            else:
                 print(f"Tag {tag} not found in the dataset.")
            return
            
        print(f"Could not interpret '{tag_identifier}' as a keyword or tag (e.g., '0010,0010').")

    except Exception as e:
         print(f"Error reading tag: {e}")

def main():
    parser = argparse.ArgumentParser(description="Check tags in a DICOM file.")
    parser.add_argument("dicom_file", help="Path to the DICOM file")
    parser.add_argument("-t", "--tag", help="Specific tag to check (e.g., 'PatientName' or '0010,0010')", default=None)
    
    args = parser.parse_args()
    
    try:
        dataset = pydicom.dcmread(args.dicom_file)
    except Exception as e:
        print(f"Error reading DICOM file '{args.dicom_file}': {e}")
        sys.exit(1)
        
    if args.tag:
        print_single_tag(dataset, args.tag)
    else:
        print_all_tags(dataset)

if __name__ == "__main__":
    main()
