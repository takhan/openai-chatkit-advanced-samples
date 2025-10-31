"""Widget rendering for structured step-by-step guides with inline images."""

from __future__ import annotations

from chatkit.widgets import Box, Card, Col, Image, Text, Title, WidgetRoot


def render_structured_guide_widget(steps: list[dict]) -> WidgetRoot:
    """Build a structured guide widget with steps and inline images.

    Args:
        steps: List of step dictionaries with structure:
            {
                "step_number": str,  # "1", "2", etc.
                "title": str,  # Step title
                "description": str,  # Detailed explanation
                "image_url": str | None  # Optional image URL
            }

    Returns:
        Widget displaying steps with inline images
    """

    # Header
    header = Box(
        padding=5,
        background="surface-tertiary",
        children=[
            Title(
                value="Step-by-Step Guide",
                size="md",
                weight="semibold",
            ),
        ],
    )

    # Create step sections
    step_sections = []
    for step in steps:
        step_num = step.get("step_number", "")
        title = step.get("title", "")
        description = step.get("description", "")
        image_url = step.get("image_url")

        # Step header (number + title)
        step_header = Text(
            value=f"Step {step_num}: {title}" if step_num else title,
            size="md",
            weight="semibold",
            color="primary",
        )

        # Step description
        step_description = Text(
            value=description,
            size="sm",
            color="secondary",
        )

        # Build step content
        step_content = [step_header, step_description]

        # Add image if provided
        if image_url:
            image_widget = Box(
                radius="lg",
                overflow="hidden",
                width="100%",
                children=[
                    Image(
                        src=image_url,
                        alt=f"Step {step_num} illustration",
                        fit="contain",
                        width="100%",
                    ),
                ],
            )
            step_content.append(image_widget)

        # Create step section
        step_section = Box(
            padding=4,
            radius="md",
            background="surface-secondary",
            children=[
                Col(
                    gap=2,
                    children=step_content,
                ),
            ],
        )

        step_sections.append(step_section)

    # Steps container
    steps_container = Box(
        padding=5,
        children=[
            Col(
                gap=3,
                children=step_sections,
            ),
        ],
    )

    return Card(
        key="structured-guide",
        padding=0,
        children=[header, steps_container],
    )


def structured_guide_widget_copy_text(steps: list[dict]) -> str:
    """Generate human-readable fallback text for the structured guide widget.

    Args:
        steps: List of step dictionaries

    Returns:
        Plain text description
    """
    lines = ["Step-by-Step Guide:\n"]

    for step in steps:
        step_num = step.get("step_number", "")
        title = step.get("title", "")
        description = step.get("description", "")
        image_url = step.get("image_url")

        # Add step header
        if step_num:
            lines.append(f"\nStep {step_num}: {title}")
        else:
            lines.append(f"\n{title}")

        # Add description
        if description:
            lines.append(description)

        # Note if image is included
        if image_url:
            lines.append("[Visual reference included]")

    return "\n".join(lines)
