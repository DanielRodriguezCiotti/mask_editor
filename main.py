import gradio as gr
import numpy as np
from PIL import Image, ImageColor


def str_color_to_rgb(str_color: str) -> tuple[int, int, int]:
    """
    Convert a string color representation to RGB tuple.

    Args:
        str_color: String representation of color (hex, name, or rgba format)

    Returns:
        tuple[int, int, int]: RGB color values as integers
    """
    try:
        # Try standard hex or color name format
        color_rgb = ImageColor.getcolor(str_color, "RGB")
    except ValueError:
        # Handle rgba format from Gradio
        if str_color.startswith("rgba("):
            # Parse rgba string manually
            rgba_values = str_color.strip("rgba()").split(",")
            # Convert to integers, handling potential float values
            r = int(float(rgba_values[0].strip()))
            g = int(float(rgba_values[1].strip()))
            b = int(float(rgba_values[2].strip()))
            color_rgb = (r, g, b)
        else:
            # Default to blue if parsing fails
            color_rgb = (0, 0, 255)
    return color_rgb  # type: ignore


def apply_mask_as_transparent_overlayer(
    mask: np.ndarray, image: Image.Image, rgb_mask_color=(0, 255, 255), transparency=0.7
):
    """
    Apply a binary mask to an image by superposing a transparent layer of color.

    Args:
        mask: A binary mask (single channel) with boolean values
        image: PIL Image object to apply the mask to
        rgb_mask_color: A tuple of three integers representing the RGB color of the mask
        transparency: Float between 0-1 representing the opacity of the mask overlay

    Returns:
        PIL Image object with the mask applied as a colored overlay
    """
    # Create a 4-channel (RGBA) array for the mask overlay
    mask_array_img = np.zeros((mask.shape[0], mask.shape[1], 4), dtype=np.uint8)
    # Set the color and transparency for masked pixels
    mask_array_img[mask] = [*rgb_mask_color, int(transparency * 255)]
    mask_img = Image.fromarray(mask_array_img)

    # Ensure the base image has an alpha channel for compositing
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Composite the overlay onto the result
    result = Image.alpha_composite(image, mask_img)

    return result.convert("RGB")


def extract_mask(canvas):
    """
    Extract a binary mask from a canvas by looking at alpha channel of the first layer.

    Args:
        canvas: A Gradio canvas object containing layers and background

    Returns:
        np.ndarray: A binary mask (boolean array) where True represents masked areas
    """
    if canvas["layers"]:
        mask_layer = canvas["layers"][0]
        # Extract pixels where alpha channel is fully opaque
        mask = np.array(mask_layer)[:, :, 3] == 255
        return mask
    else:
        # Return empty mask if no layers exist
        return np.zeros(
            (canvas["background"].height, canvas["background"].width), dtype=np.uint8
        ).astype(bool)


def canvas_to_mask_visibility(canvas, mask_color: str):
    """
    Create a visualization of the mask overlaid on the original image.

    Args:
        canvas: Gradio canvas object containing the image and mask
        mask_color: String representation of the color to use for the mask

    Returns:
        PIL.Image: Original image with colored mask overlay
    """
    original_image = canvas["background"]
    mask = extract_mask(canvas)
    rgb_mask_color = str_color_to_rgb(mask_color)
    return apply_mask_as_transparent_overlayer(mask, original_image, rgb_mask_color)


def canvas_to_agnostic(canvas):
    """
    Create an agnostic visualization of the mask using a gray overlay.

    Args:
        canvas: Gradio canvas object containing the image and mask

    Returns:
        PIL.Image: Original image with gray mask overlay at full opacity
    """
    original_image = canvas["background"]
    mask = extract_mask(canvas)
    return apply_mask_as_transparent_overlayer(mask, original_image, (128, 128, 128), 1)


def canvas_to_mask(canvas):
    """
    Extract the binary mask from the canvas and convert to an image.

    Args:
        canvas: Gradio canvas object containing the image and mask

    Returns:
        PIL.Image: Binary mask as a black and white image
    """
    mask = extract_mask(canvas)
    return Image.fromarray(mask.astype(np.uint8) * 255)


def apply_mask_to_layer(mask_image, canvas):
    """
    Apply an uploaded mask image to the canvas layer.

    Args:
        mask_image: PIL Image containing the mask to apply
        canvas: Gradio canvas object to apply the mask to

    Returns:
        Updated canvas object with the mask applied to the first layer
    """
    # Check if canvas background is empty
    is_canvas_empty = np.all(np.array(canvas["background"]) == 0)
    if is_canvas_empty:
        # Create a new transparent background if none exists
        canvas["background"] = Image.new(
            "RGBA", (mask_image.width, mask_image.height), 0
        )

    # Create a new layer with gray color where the mask is white
    layer = np.zeros((mask_image.height, mask_image.width, 4), dtype=np.uint8)
    layer[np.array(mask_image.convert("L")) == 255] = [128, 128, 128, 255]
    canvas["layers"][0] = Image.fromarray(layer)
    return canvas


with gr.Blocks() as demo:
    gr.Markdown("# Mask Editor")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## How to use")
            gr.Markdown("1. Upload your background image on the canvas")
            gr.Markdown("2. (Optional) Upload a mask image to start from if available")
            gr.Markdown(
                "3. Edit the mask on the canvas using the brush tool and the eraser tool"
            )
            gr.Markdown(
                "4. Three different outputs will be rendered automatically so you can download them as needed"
            )
        with gr.Column(scale=1):
            canvas = gr.ImageEditor(
                label="Canvas",
                type="pil",
                mirror_webcam=False,
                brush=gr.Brush(
                    colors=["#808080"], color_mode="fixed", default_color="#808080"
                ),
                layers=False,
                image_mode="RGBA",
            )

        with gr.Column(scale=1):
            mask_image = gr.Image(
                label="Mask Image (Optional)",
                type="pil",
                image_mode="RGB",
            )
    with gr.Row():
        with gr.Column(scale=1):
            mask_visibility_image = gr.Image(
                label="Mask Visibility Image",
                type="pil",
                image_mode="RGB",
                format="webp",
            )
            mask_color = gr.ColorPicker(
                label="Mask Color",
                value="#20ff03",
            )
        with gr.Column(scale=1):
            agnostic_image = gr.Image(
                label="Agnostic Image",
                type="pil",
                image_mode="RGB",
                format="webp",
            )
        with gr.Column(scale=1):
            output_mask = gr.Image(
                label="Output Mask",
                type="pil",
                image_mode="RGB",
                format="png",
            )
    mask_image.upload(apply_mask_to_layer, outputs=canvas, inputs=[mask_image, canvas])
    mask_color.change(
        canvas_to_mask_visibility,
        outputs=mask_visibility_image,
        inputs=[canvas, mask_color],
    )
    canvas.change(
        canvas_to_mask_visibility,
        outputs=mask_visibility_image,
        inputs=[canvas, mask_color],
    )
    canvas.change(canvas_to_agnostic, outputs=agnostic_image, inputs=canvas)
    canvas.change(canvas_to_mask, outputs=output_mask, inputs=canvas)


if __name__ == "__main__":
    demo.launch()
