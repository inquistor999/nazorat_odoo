import os
from PIL import Image, ImageDraw, ImageFont
import datetime

def generate_receipt_image(items, location_from, location_to, company_from="B2B", company_to="Urikzor", timestamp=None):
    """
    Generates a professional receipt image listing multiple items.
    items: list of dicts [{'name': 'Muzqaymoq...', 'qty': 150}, ...]
    """
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
    # Calculate height based on number of items
    header_height = 180
    footer_height = 80
    row_height = 35
    total_qty = sum(float(item.get('qty', 0)) for item in items)
    
    # Base height + space for items + total line
    height = header_height + (len(items) * row_height) + 60 + footer_height
    width = 700
    
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, otherwise use default
    try:
        font_title = ImageFont.truetype("arial.ttf", 32)
        font_body = ImageFont.truetype("arial.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 16)
        font_bold = ImageFont.truetype("arialbd.ttf", 22)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_bold = ImageFont.load_default()
    
    # Draw header
    draw.rectangle([0, 0, width, 60], fill=(0, 102, 204))
    draw.text((20, 15), "INTERCOMPANY TRANSFER", fill=(255, 255, 255), font=font_title)
    
    # Info Section
    y_offset = 75
    draw.text((20, y_offset), f"Date: {timestamp}", fill=(100, 100, 100), font=font_small)
    y_offset += 25
    draw.text((20, y_offset), f"Source: {company_from} ({location_from})", fill=(0, 0, 0), font=font_body)
    y_offset += 25
    draw.text((20, y_offset), f"Destination: {company_to} ({location_to})", fill=(0, 0, 0), font=font_body)
    y_offset += 35
    
    # Draw a line
    draw.line([(20, y_offset), (width-20, y_offset)], fill=(200, 200, 200), width=2)
    y_offset += 15
    
    # Table Header
    draw.text((20, y_offset), "Product", fill=(100, 100, 100), font=font_small)
    draw.text((width - 150, y_offset), "Quantity", fill=(100, 100, 100), font=font_small)
    y_offset += 25
    draw.line([(20, y_offset), (width-20, y_offset)], fill=(220, 220, 220), width=1)
    y_offset += 15
    
    # Items
    for i, item in enumerate(items):
        name = item.get('matched_name') or item.get('raw_name') or "Unknown Product"
        if len(name) > 45:
            name = name[:45] + "..."
        qty = item.get('qty', 0)
        
        draw.text((20, y_offset), f"{i+1}. {name}", fill=(0, 51, 102), font=font_body)
        draw.text((width - 150, y_offset), f"{qty} KG", fill=(0, 0, 0), font=font_bold)
        y_offset += row_height
        
    draw.line([(20, y_offset), (width-20, y_offset)], fill=(200, 200, 200), width=2)
    y_offset += 15
    
    # Total
    draw.text((20, y_offset), "TOTAL QUANTITY:", fill=(0, 0, 0), font=font_bold)
    draw.text((width - 150, y_offset), f"{total_qty} KG", fill=(0, 153, 51), font=font_title)
    
    # Draw footer
    draw.rectangle([0, height-40, width, height], fill=(240, 240, 240))
    draw.text((20, height-30), "Generated automatically via AI System", fill=(150, 150, 150), font=font_small)
    
    # Save the image in temp dir
    filename = f"receipt_{int(datetime.datetime.now().timestamp())}.png"
    filepath = os.path.join(os.getcwd(), filename)
    image.save(filepath)
    return filepath
