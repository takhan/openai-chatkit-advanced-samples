"""Widget rendering for Standard Operating Procedures."""

from __future__ import annotations

from chatkit.widgets import Box, Card, Col, Image, Row, Text, Title, WidgetComponent, WidgetRoot

from .sops import SOP


def render_sop_widget(sop: SOP) -> WidgetRoot:
    """Build a SOP display widget with content and images."""

    # Header with SOP title and category
    header = Box(
        padding=5,
        background="surface-tertiary",
        children=[
            Col(
                gap=2,
                children=[
                    Row(
                        justify="between",
                        align="center",
                        children=[
                            Title(
                                value=sop.title,
                                size="md",
                                weight="semibold",
                            ),
                            Box(
                                padding=2,
                                radius="lg",
                                background="blue-100",
                                children=[
                                    Text(
                                        value=sop.category,
                                        size="xs",
                                        weight="medium",
                                        color="blue-700",
                                    )
                                ],
                            ),
                        ],
                    ),
                    Text(
                        value=f"Last updated: {sop.last_updated or 'N/A'}",
                        size="xs",
                        color="tertiary",
                    ),
                ],
            ),
        ],
    )

    # SOP content section
    content_section = Box(
        padding=5,
        children=[
            Col(
                gap=3,
                children=[
                    Text(value="Instructions", weight="semibold", size="sm"),
                    Text(
                        value=sop.content,
                        size="sm",
                        color="secondary",
                    ),
                ],
            ),
        ],
    )

    # Images section (if images exist)
    body_children: list[WidgetComponent] = [content_section]

    if sop.images:
        image_widgets = [
            Box(
                radius="lg",
                overflow="hidden",
                width="100%",
                children=[
                    Image(
                        src=img_url,
                        alt=f"{sop.title} - Image {idx + 1}",
                        fit="contain",
                        width="100%",
                    )
                ],
            )
            for idx, img_url in enumerate(sop.images)
        ]

        images_section = Box(
            padding=5,
            children=[
                Col(
                    gap=3,
                    children=[
                        Text(value="Reference Images", weight="semibold", size="sm"),
                        Col(gap=3, children=image_widgets),
                    ],
                ),
            ],
        )
        body_children.append(images_section)

    return Card(
        key=f"sop-{sop.id}",
        padding=0,
        children=[header] + body_children,
    )


def sop_widget_copy_text(sop: SOP) -> str:
    """Generate human-readable fallback text for the SOP widget."""

    segments: list[str] = []

    # Title and category
    segments.append(f"SOP: {sop.title}")
    segments.append(f"Category: {sop.category}")

    if sop.last_updated:
        segments.append(f"Last updated: {sop.last_updated}")

    # Content
    segments.append(f"\n{sop.content}")

    # Images info
    if sop.images:
        image_count = len(sop.images)
        segments.append(f"\n{image_count} reference image(s) attached.")

    # Keywords
    if sop.keywords:
        keywords_str = ", ".join(sop.keywords)
        segments.append(f"Keywords: {keywords_str}")

    return "\n".join(segments).strip()
