from PIL import Image, ImageOps, ImageFilter
import os

def resize_image(image_path, output_path, size=(1024, 1024)):
    """Resize an image to a specific size."""
    with Image.open(image_path) as img:
        img = img.resize(size, Image.Resampling.LANCZOS)
        img.save(output_path)
        print(f"Resized image saved to {output_path}")

def apply_sepia(image_path, output_path):
    """Apply a sepia-like filter to an image for a 'vintage map' look."""
    with Image.open(image_path) as img:
        # Convert to grayscale
        gray = ImageOps.grayscale(img)
        # Apply sepia tint
        sepia = ImageOps.colorize(gray, "#704214", "#C0A080")
        sepia.save(output_path)
        print(f"Sepia image saved to {output_path}")

def add_border(image_path, output_path, border_width=20, color="black"):
    """Add a border to an image."""
    with Image.open(image_path) as img:
        bordered = ImageOps.expand(img, border=border_width, fill=color)
        bordered.save(output_path)
        print(f"Bordered image saved to {output_path}")
