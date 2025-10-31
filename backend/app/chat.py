"""ChatKit server integration for the boilerplate backend."""

from __future__ import annotations

import inspect
import logging
from datetime import datetime
from typing import Annotated, Any, AsyncIterator, Final, Literal
from uuid import uuid4

from agents import Agent, RunContextWrapper, Runner, function_tool
from chatkit.agents import (
    AgentContext,
    ClientToolCall,
    ThreadItemConverter,
    stream_agent_response,
)
from chatkit.server import ChatKitServer, ThreadItemDoneEvent
from chatkit.types import (
    Attachment,
    ClientToolCallItem,
    HiddenContextItem,
    ThreadItem,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from openai.types.responses import ResponseInputContentParam
from pydantic import BaseModel, ConfigDict, Field

from .constants import MODEL, get_seller_assistant_instructions
from .facts import Fact, fact_store
from .memory_store import MemoryStore
from .reference_images_widget import (
    reference_images_widget_copy_text,
    render_reference_images_widget,
)
from .sample_widget import render_weather_widget, weather_widget_copy_text
from .sop_widget import render_sop_widget, sop_widget_copy_text
from .sops import get_formatted_sop_toc, sop_s3_client
from .structured_guide_widget import (
    render_structured_guide_widget,
    structured_guide_widget_copy_text,
)
from .weather import (
    WeatherLookupError,
    retrieve_weather,
)
from .weather import (
    normalize_unit as normalize_temperature_unit,
)

# If you want to check what's going on under the hood, set this to DEBUG
logging.basicConfig(level=logging.INFO)

SUPPORTED_COLOR_SCHEMES: Final[frozenset[str]] = frozenset({"light", "dark"})
CLIENT_THEME_TOOL_NAME: Final[str] = "switch_theme"


def _normalize_color_scheme(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in SUPPORTED_COLOR_SCHEMES:
        return normalized
    if "dark" in normalized:
        return "dark"
    if "light" in normalized:
        return "light"
    raise ValueError("Theme must be either 'light' or 'dark'.")


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _is_tool_completion_item(item: Any) -> bool:
    return isinstance(item, ClientToolCallItem)


class FactAgentContext(AgentContext):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    store: Annotated[MemoryStore, Field(exclude=True)]
    request_context: dict[str, Any]


class GuideStep(BaseModel):
    """Represents a single step in a structured guide."""
    step_number: str
    title: str
    description: str
    image_url: str | None = None


async def _stream_saved_hidden(ctx: RunContextWrapper[FactAgentContext], fact: Fact) -> None:
    await ctx.context.stream(
        ThreadItemDoneEvent(
            item=HiddenContextItem(
                id=_gen_id("msg"),
                thread_id=ctx.context.thread.id,
                created_at=datetime.now(),
                content=(
                    f'<FACT_SAVED id="{fact.id}" threadId="{ctx.context.thread.id}">{fact.text}</FACT_SAVED>'
                ),
            ),
        )
    )


@function_tool(description_override="Record a fact shared by the user so it is saved immediately.")
async def save_fact(
    ctx: RunContextWrapper[FactAgentContext],
    fact: str,
) -> dict[str, str] | None:
    try:
        saved = await fact_store.create(text=fact)
        confirmed = await fact_store.mark_saved(saved.id)
        if confirmed is None:
            raise ValueError("Failed to save fact")
        await _stream_saved_hidden(ctx, confirmed)
        ctx.context.client_tool_call = ClientToolCall(
            name="record_fact",
            arguments={"fact_id": confirmed.id, "fact_text": confirmed.text},
        )
        print(f"FACT SAVED: {confirmed}")
        return {"fact_id": confirmed.id, "status": "saved"}
    except Exception:
        logging.exception("Failed to save fact")
        return None


@function_tool(
    description_override="Switch the chat interface between light and dark color schemes."
)
async def switch_theme(
    ctx: RunContextWrapper[FactAgentContext],
    theme: str,
) -> dict[str, str] | None:
    logging.debug(f"Switching theme to {theme}")
    try:
        requested = _normalize_color_scheme(theme)
        ctx.context.client_tool_call = ClientToolCall(
            name=CLIENT_THEME_TOOL_NAME,
            arguments={"theme": requested},
        )
        return {"theme": requested}
    except Exception:
        logging.exception("Failed to switch theme")
        return None


@function_tool(
    description_override="Retrieve internal SOP content for your reference. Returns the procedure text and image URLs. This information is for your use only - do not display it to the user or mention SOP names."
)
async def get_sop(
    ctx: RunContextWrapper[FactAgentContext],
    sop_id: str,
) -> dict[str, str | list[str]]:
    """Fetch SOP content from S3. Returns content and image URLs for agent to use privately."""
    print(f"[SOPTool] tool invoked with sop_id={sop_id}")

    try:
        # Fetch SOP from S3
        sop = await sop_s3_client.get_sop(sop_id)

        if sop is None:
            error_msg = f"SOP '{sop_id}' not found in the library. Please check the SOP ID and try again."
            print(f"[SOPTool] {error_msg}")
            raise ValueError(error_msg)

        print(f"[SOPTool] SOP retrieved: {sop.title}")
        print(f"[SOPTool] Returning content ({len(sop.content)} chars) and {len(sop.images)} images to agent")

        # Return content and images to agent (not displayed to user)
        return {
            "sop_id": sop.id,
            "title": sop.title,
            "category": sop.category,
            "content": sop.content,
            "image_urls": sop.images,
            "image_count": str(len(sop.images)),
        }

    except ValueError as exc:
        # Re-raise ValueError for agent to handle
        print(f"[SOPTool] ValueError: {str(exc)}")
        raise
    except Exception as exc:
        error_msg = f"Failed to retrieve SOP '{sop_id}': {str(exc)}"
        print(f"[SOPTool] Unexpected error: {error_msg}")
        raise ValueError(error_msg) from exc


@function_tool(
    description_override="Display reference images to help the user understand the steps. Pass the image URLs you collected from get_sop calls. Images will be numbered sequentially."
)
async def show_reference_images(
    ctx: RunContextWrapper[FactAgentContext],
    image_urls: list[str],
) -> dict[str, str]:
    """Display a gallery of numbered reference images for the user.

    Args:
        image_urls: List of pre-signed S3 URLs from SOPs retrieved earlier

    Returns:
        Status indicating images were displayed
    """
    print(f"[ReferenceImagesTool] tool invoked with {len(image_urls)} images")

    try:
        if not image_urls:
            print("[ReferenceImagesTool] No images provided, skipping widget")
            return {"status": "no_images", "message": "No images to display"}

        # Render the reference images widget
        widget = render_reference_images_widget(image_urls)
        copy_text = reference_images_widget_copy_text(image_urls)

        # Stream the widget to the UI
        await ctx.context.stream_widget(widget, copy_text=copy_text)

        print(f"[ReferenceImagesTool] Successfully displayed {len(image_urls)} images")

        return {
            "status": "success",
            "image_count": str(len(image_urls)),
            "message": f"Displayed {len(image_urls)} reference images",
        }

    except Exception as exc:
        error_msg = f"Failed to display reference images: {str(exc)}"
        print(f"[ReferenceImagesTool] Error: {error_msg}")
        raise ValueError(error_msg) from exc


@function_tool(
    description_override="Display a structured step-by-step guide with inline images. Use this for multi-step procedures where each step has associated images. Pass a list of steps with their descriptions and image URLs."
)
async def show_structured_guide(
    ctx: RunContextWrapper[FactAgentContext],
    steps: list[GuideStep],
) -> dict[str, str]:
    """Display a structured guide with steps and inline images.

    Args:
        steps: List of GuideStep objects with step_number, title, description, and optional image_url

    Returns:
        Status indicating guide was displayed
    """
    print(f"[StructuredGuideTool] tool invoked with {len(steps)} steps")

    try:
        if not steps:
            print("[StructuredGuideTool] No steps provided, skipping widget")
            return {"status": "no_steps", "message": "No steps to display"}

        # Convert Pydantic models to dicts for the widget renderer
        steps_dicts = [step.model_dump() for step in steps]

        # Count steps with images
        steps_with_images = sum(1 for step in steps if step.image_url)

        # Render the structured guide widget
        widget = render_structured_guide_widget(steps_dicts)
        copy_text = structured_guide_widget_copy_text(steps_dicts)

        # Stream the widget to the UI
        await ctx.context.stream_widget(widget, copy_text=copy_text)

        print(
            f"[StructuredGuideTool] Successfully displayed {len(steps)} steps "
            f"({steps_with_images} with images)"
        )

        return {
            "status": "success",
            "step_count": str(len(steps)),
            "image_count": str(steps_with_images),
            "message": f"Displayed {len(steps)} steps with {steps_with_images} images",
        }

    except Exception as exc:
        error_msg = f"Failed to display structured guide: {str(exc)}"
        print(f"[StructuredGuideTool] Error: {error_msg}")
        raise ValueError(error_msg) from exc


@function_tool(
    description_override="Look up the current weather and upcoming forecast for a location and render an interactive weather dashboard."
)
async def get_weather(
    ctx: RunContextWrapper[FactAgentContext],
    location: str,
    unit: Literal["celsius", "fahrenheit"] | str | None = None,
) -> dict[str, str | None]:
    print("[WeatherTool] tool invoked", {"location": location, "unit": unit})
    try:
        normalized_unit = normalize_temperature_unit(unit)
    except WeatherLookupError as exc:
        print("[WeatherTool] invalid unit", {"error": str(exc)})
        raise ValueError(str(exc)) from exc

    try:
        data = await retrieve_weather(location, normalized_unit)
    except WeatherLookupError as exc:
        print("[WeatherTool] lookup failed", {"error": str(exc)})
        raise ValueError(str(exc)) from exc

    print(
        "[WeatherTool] lookup succeeded",
        {
            "location": data.location,
            "temperature": data.temperature,
            "unit": data.temperature_unit,
        },
    )
    try:
        widget = render_weather_widget(data)
        copy_text = weather_widget_copy_text(data)
        payload: Any
        try:
            payload = widget.model_dump()
        except AttributeError:
            payload = widget
        print("[WeatherTool] widget payload", payload)
    except Exception as exc:  # noqa: BLE001
        print("[WeatherTool] widget build failed", {"error": str(exc)})
        raise ValueError("Weather data is currently unavailable for that location.") from exc

    print("[WeatherTool] streaming widget")
    try:
        await ctx.context.stream_widget(widget, copy_text=copy_text)
    except Exception as exc:  # noqa: BLE001
        print("[WeatherTool] widget stream failed", {"error": str(exc)})
        raise ValueError("Weather data is currently unavailable for that location.") from exc

    print("[WeatherTool] widget streamed")

    observed = data.observation_time.isoformat() if data.observation_time else None

    return {
        "location": data.location,
        "unit": normalized_unit,
        "observed_at": observed,
    }


def _user_message_text(item: UserMessageItem) -> str:
    parts: list[str] = []
    for part in item.content:
        text = getattr(part, "text", None)
        if text:
            parts.append(text)
    return " ".join(parts).strip()


class FactAssistantServer(ChatKitServer[dict[str, Any]]):
    """ChatKit server wired up with the SOP retrieval tool."""

    def __init__(self) -> None:
        self.store: MemoryStore = MemoryStore()
        super().__init__(self.store)

        # Get SOP table of contents for instructions
        sop_toc = get_formatted_sop_toc()
        instructions = get_seller_assistant_instructions(sop_toc)

        # Tools for Seller Assistant
        tools = [get_sop, show_structured_guide, show_reference_images, switch_theme]

        self.assistant = Agent[FactAgentContext](
            model=MODEL,
            name="Seller Assistant",
            instructions=instructions,
            tools=tools,  # type: ignore[arg-type]
        )
        self._thread_item_converter = self._init_thread_item_converter()

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        agent_context = FactAgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        target_item: ThreadItem | None = item
        if target_item is None:
            target_item = await self._latest_thread_item(thread, context)

        if target_item is None or _is_tool_completion_item(target_item):
            return

        agent_input = await self._to_agent_input(thread, target_item)
        if agent_input is None:
            return

        result = Runner.run_streamed(
            self.assistant,
            agent_input,
            context=agent_context,
        )

        async for event in stream_agent_response(agent_context, result):
            yield event
        return

    async def to_message_content(self, _input: Attachment) -> ResponseInputContentParam:
        raise RuntimeError("File attachments are not supported in this demo.")

    def _init_thread_item_converter(self) -> Any | None:
        converter_cls = ThreadItemConverter
        if converter_cls is None or not callable(converter_cls):
            return None

        attempts: tuple[dict[str, Any], ...] = (
            {"to_message_content": self.to_message_content},
            {"message_content_converter": self.to_message_content},
            {},
        )

        for kwargs in attempts:
            try:
                return converter_cls(**kwargs)
            except TypeError:
                continue
        return None

    async def _latest_thread_item(
        self, thread: ThreadMetadata, context: dict[str, Any]
    ) -> ThreadItem | None:
        try:
            items = await self.store.load_thread_items(thread.id, None, 1, "desc", context)
        except Exception:  # pragma: no cover - defensive
            return None

        return items.data[0] if getattr(items, "data", None) else None

    async def _to_agent_input(
        self,
        thread: ThreadMetadata,
        item: ThreadItem,
    ) -> Any | None:
        if _is_tool_completion_item(item):
            return None

        converter = getattr(self, "_thread_item_converter", None)
        if converter is not None:
            for attr in (
                "to_input_item",
                "convert",
                "convert_item",
                "convert_thread_item",
            ):
                method = getattr(converter, attr, None)
                if method is None:
                    continue
                call_args: list[Any] = [item]
                call_kwargs: dict[str, Any] = {}
                try:
                    signature = inspect.signature(method)
                except (TypeError, ValueError):
                    signature = None

                if signature is not None:
                    params = [
                        parameter
                        for parameter in signature.parameters.values()
                        if parameter.kind
                        not in (
                            inspect.Parameter.VAR_POSITIONAL,
                            inspect.Parameter.VAR_KEYWORD,
                        )
                    ]
                    if len(params) >= 2:
                        next_param = params[1]
                        if next_param.kind in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        ):
                            call_args.append(thread)
                        else:
                            call_kwargs[next_param.name] = thread

                result = method(*call_args, **call_kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result

        if isinstance(item, UserMessageItem):
            return _user_message_text(item)

        return None

    async def _add_hidden_item(
        self,
        thread: ThreadMetadata,
        context: dict[str, Any],
        content: str,
    ) -> None:
        await self.store.add_thread_item(
            thread.id,
            HiddenContextItem(
                id=_gen_id("msg"),
                thread_id=thread.id,
                created_at=datetime.now(),
                content=content,
            ),
            context,
        )


def create_chatkit_server() -> FactAssistantServer | None:
    """Return a configured ChatKit server instance if dependencies are available."""
    return FactAssistantServer()
