#!/usr/bin/env python3
"""
Create a test PDF for demonstration purposes
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import os

def create_test_pdf():
    """Create a simple test PDF with some content"""
    
    # Create a simple PDF with text
    filename = "test_document.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Page 1 - Good quality text
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "PDF Scan Quality Checker - Test Document")
    
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 150, "This is a test document for the PDF quality analysis system.")
    c.drawString(100, height - 180, "Page 1: This page should have good quality scores.")
    c.drawString(100, height - 210, "The text is clear and well-formatted.")
    c.drawString(100, height - 240, "No blur, proper orientation, good cropping.")
    
    # Add some content to make it more realistic
    for i in range(10):
        y_pos = height - 280 - (i * 20)
        c.drawString(100, y_pos, f"Line {i+1}: This is sample text for quality analysis.")
    
    c.showPage()
    
    # Page 2 - Simulate some issues
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 100, "Page 2: Testing Quality Detection")
    
    c.setFont("Helvetica", 10)
    c.drawString(100, height - 150, "This page might have some quality issues.")
    c.drawString(100, height - 180, "The text is smaller and might be harder to read.")
    c.drawString(100, height - 210, "This could affect the blur detection algorithm.")
    
    # Add rotated text to test orientation detection
    c.saveState()
    c.translate(200, 300)
    c.rotate(15)  # Rotate 15 degrees
    c.setFont("Helvetica", 12)
    c.drawString(0, 0, "Rotated text for orientation testing")
    c.restoreState()
    
    c.showPage()
    
    # Page 3 - More content
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 100, "Page 3: Additional Content")
    
    c.setFont("Helvetica", 11)
    for i in range(15):
        y_pos = height - 140 - (i * 18)
        c.drawString(100, y_pos, f"Content line {i+1}: Testing multiple pages for analysis.")
    
    c.save()
    
    print(f"✅ Created test PDF: {filename}")
    print(f"📄 File size: {os.path.getsize(filename)} bytes")
    print(f"📍 Location: {os.path.abspath(filename)}")
    
    return filename

if __name__ == "__main__":
    try:
        create_test_pdf()
    except ImportError:
        print("❌ Error: reportlab is not installed")
        print("Install it with: pip install reportlab")
        print("Or use the system without creating a test PDF")
    except Exception as e:
        print(f"❌ Error creating test PDF: {e}")
