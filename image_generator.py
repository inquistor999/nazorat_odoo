import os
from PIL import Image, ImageDraw, ImageFont
import datetime

def generate_receipt_image(product_name, qty, location_from, location_to, timestamp=None):
    """
    Generates a professional receipt image for an order/transfer.
    """
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
    # Create a blank image with white background
    width, height = 600, 400
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, otherwise use default
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_body = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw header
    draw.rectangle([0, 0, width, 80], fill=(0, 102, 204))
    draw.text((20, 20), "YANGI ZAKAZ TASDIQLANDI", fill=(255, 255, 255), font=font_title)
    
    # Draw content
    y_offset = 110
    draw.text((20, y_offset), f"Sana: {timestamp}", fill=(100, 100, 100), font=font_small)
    y_offset += 40
    
    draw.text((20, y_offset), f"Qayerdan: {location_from}", fill=(0, 0, 0), font=font_body)
    y_offset += 40
    draw.text((20, y_offset), f"Qayerga: {location_to}", fill=(0, 0, 0), font=font_body)
    y_offset += 50
    
    # Draw a line
    draw.line([(20, y_offset), (width-20, y_offset)], fill=(200, 200, 200), width=2)
    y_offset += 20
    
    draw.text((20, y_offset), "Tovar nomi:", fill=(100, 100, 100), font=font_small)
    y_offset += 25
    draw.text((20, y_offset), product_name, fill=(0, 51, 102), font=font_body)
    y_offset += 40
    
    draw.text((20, y_offset), "Miqdori:", fill=(100, 100, 100), font=font_small)
    y_offset += 25
    draw.text((20, y_offset), f"{qty} kg / dona", fill=(0, 153, 51), font=font_title)
    
    # Draw footer
    draw.rectangle([0, height-40, width, height], fill=(240, 240, 240))
    draw.text((20, height-30), "Tizim orqali avtomatik yaratildi", fill=(150, 150, 150), font=font_small)
    
    # Save the image in temp dir
    filename = f"receipt_{int(datetime.datetime.now().timestamp())}.png"
    filepath = os.path.join(os.getcwd(), filename)
    image.save(filepath)
    return filepath

if __name__ == '__main__':
    # Test
    path = generate_receipt_image("Oq Qand (Shakar)", "500", "B2B Sklad-1", "O'rikzor")
    print("Test image generated at:", path)
