"""Widget rendering for reference images."""

from __future__ import annotations

from chatkit.widgets import Box, Card, Col, Image, Text, Title, WidgetRoot


def render_reference_images_widget(image_urls: list[str]) -> WidgetRoot:
    """Build a simple gallery widget displaying numbered reference images.

    Args:
        image_urls: List of pre-signed S3 URLs for images

    Returns:
        Widget displaying numbered images in a grid
    """

    # Header
    header = Box(
        padding=5,
        background="surface-tertiary",
        children=[
            Title(
                value="Reference Images",
                size="md",
                weight="semibold",
            ),
        ],
    )

    # Create image widgets
    image_widgets = []
    for idx, img_url in enumerate(image_urls, start=1):
        image_widget = Box(
            radius="lg",
            overflow="hidden",
            width="100%",
            children=[
                Col(
                    gap=2,
                    children=[
                        Text(
                            value=f"Reference Image {idx}",
                            size="sm",
                            weight="medium",
                            color="secondary",
                        ),
                        Image(
                            src=img_url,
                            alt=f"Reference Image {idx}",
                            fit="contain",
                            width="100%",
                        ),
                    ],
                ),
            ],
        )
        image_widgets.append(image_widget)

    # Images section
    images_section = Box(
        padding=5,
        children=[
            Col(
                gap=3,
                children=image_widgets,
            ),
        ],
    )

    return Card(
        key="reference-images",
        padding=0,
        children=[header, images_section],
    )


def reference_images_widget_copy_text(image_urls: list[str]) -> str:
    """Generate human-readable fallback text for the reference images widget.

    Args:
        image_urls: List of image URLs

    Returns:
        Plain text description
    """
    image_count = len(image_urls)

    if image_count == 0:
        return "No reference images available."
    elif image_count == 1:
        return "Reference Image 1 is displayed above for visual guidance."
    else:
        return f"Reference Images 1-{image_count} are displayed above for visual guidance."
