import os
from pathlib import Path
from typing import List, Optional
import typer
from fpdf import FPDF
from PIL import Image

app = typer.Typer(help="D&D Portrait PDF Generator")

def get_image_files(directory: Path) -> List[Path]:
    """Get all image files from a directory."""
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return [
        p for p in directory.iterdir() 
        if p.suffix.lower() in extensions
    ]


def generate_pdf_from_dir(
    *,
    input_dir: Path,
    output_pdf: Path,
    columns: int = 2,
    rows: int = 3,
    margin: float = 10.0,
    spacing: float = 5.0,
) -> None:
    """Generate a PDF with portraits arranged in a grid on A4 pages."""
    if not input_dir.is_dir():
        raise ValueError(f"{input_dir} is not a directory")

    images = get_image_files(input_dir)
    if not images:
        raise ValueError(f"No images found in {input_dir}")

    # A4 dimensions in mm
    PAGE_WIDTH = 210
    PAGE_HEIGHT = 297

    # Calculate available space
    available_width = PAGE_WIDTH - (2 * margin) - ((columns - 1) * spacing)
    available_height = PAGE_HEIGHT - (2 * margin) - ((rows - 1) * spacing)

    img_w = available_width / columns
    img_h = available_height / rows

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)

    count = 0
    for img_path in images:
        # Start a new page if needed
        if count % (columns * rows) == 0:
            pdf.add_page()

        # Calculate position
        idx_on_page = count % (columns * rows)
        col = idx_on_page % columns
        row = idx_on_page // columns

        x = margin + (col * (img_w + spacing))
        y = margin + (row * (img_h + spacing))

        # Use PIL to check image aspect ratio and fit it
        with Image.open(img_path) as img:
            w, h = img.size
            aspect = w / h

            # Fit image within the cell while maintaining aspect ratio
            target_w = img_w
            target_h = img_w / aspect

            if target_h > img_h:
                target_h = img_h
                target_w = img_h * aspect

            # Center image in its cell
            offset_x = (img_w - target_w) / 2
            offset_y = (img_h - target_h) / 2

            pdf.image(str(img_path), x + offset_x, y + offset_y, w=target_w, h=target_h)

        count += 1

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_pdf))

@app.command()
def generate(
    input_dir: Path = typer.Argument(..., help="Directory containing character portraits"),
    output_pdf: Path = typer.Option("portraits.pdf", "--output", "-o", help="Output PDF file path"),
    columns: int = typer.Option(2, "--cols", "-c", help="Number of columns per page"),
    rows: int = typer.Option(3, "--rows", "-r", help="Number of rows per page"),
    margin: float = typer.Option(10.0, "--margin", "-m", help="Page margin in mm"),
    spacing: float = typer.Option(5.0, "--spacing", "-s", help="Spacing between images in mm"),
):
    """
    Generate a PDF with character portraits arranged in a grid on A4 pages.
    """
    if not input_dir.is_dir():
        typer.echo(f"Error: {input_dir} is not a directory.", err=True)
        raise typer.Exit(code=1)

    images = get_image_files(input_dir)
    if not images:
        typer.echo(f"No images found in {input_dir}.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(images)} images. Generating PDF...")

    try:
        generate_pdf_from_dir(
            input_dir=input_dir,
            output_pdf=output_pdf,
            columns=columns,
            rows=rows,
            margin=margin,
            spacing=spacing,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Successfully created {output_pdf}")

if __name__ == "__main__":
    app()
