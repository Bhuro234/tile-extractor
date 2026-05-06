import fitz
import sys

try:
    pdf_path = r"C:\Users\somya\Downloads\my_folder\catalogue.pdf"
    print(f"Opening: {pdf_path}", file=sys.stderr)
    sys.stderr.flush()
    
    doc = fitz.open(pdf_path)
    print(f"✓ File opened. Total pages: {len(doc)}", file=sys.stderr)
    sys.stderr.flush()
    
    print("\n" + "="*70)
    print("PAGE 1 RAW TEXT")
    print("="*70 + "\n")
    
    text = doc[0].get_text()
    lines = text.split('\n')
    for i, line in enumerate(lines[:100]):  # First 100 lines
        print(f"{i+1:3d}: {line}")
    
    if len(lines) > 100:
        print(f"\n... ({len(lines) - 100} more lines)")
    
    doc.close()
    print("\n✓ Done", file=sys.stderr)
    
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
