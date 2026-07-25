"""
Logo Compositor Service for Wayne AI Video Studio.

Flow:
1. Flux generates background image
2. GPT-4o vision analyzes image + logo + prompt
3. GPT decides best placement position and size
4. Pillow composites real logo onto background
5. Returns final branded image
"""
import asyncio
import base64
import io
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGES_DIR = Path("static/images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def _download_image_bytes(url: str) -> bytes | None:
    """Download image from URL or decode from data URL."""
    try:
        if url.startswith("data:"):
            # Base64 data URL
            header, data = url.split(",", 1)
            return base64.b64decode(data)
        else:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None


async def _ask_gpt_logo_placement(
    background_url: str,
    logo_url: str,
    prompt: str,
) -> dict:
    """
    Decide logo placement using smart rules first, GPT as enhancement if available.
    """
    # Smart rules-based placement (works without OpenAI)
    prompt_lower = prompt.lower()

    # Default placements based on content type
    if any(w in prompt_lower for w in ["villa", "property", "real estate", "house", "apartment", "building"]):
        position = "top-right"
        size = 12
    elif any(w in prompt_lower for w in ["product", "bottle", "perfume", "food", "restaurant"]):
        position = "bottom-right"
        size = 15
    elif any(w in prompt_lower for w in ["fashion", "model", "person", "portrait"]):
        position = "top-left"
        size = 12
    elif any(w in prompt_lower for w in ["salon", "beauty", "spa"]):
        position = "bottom-center"
        size = 18
    else:
        position = "top-right"
        size = 12

    default_placement = {
        "position": position,
        "size_percent": size,
        "margin_percent": 2,
        "reasoning": "smart rules based placement"
    }

    # Try GPT for enhanced placement if OpenAI available
    try:
        client = _get_openai_client()
        content = [
            {
                "type": "text",
                "text": (
                    f"Advertisement image for: '{prompt}'\n"
                    f"Where should I place the brand logo for best visual impact?\n"
                    f"Respond ONLY with JSON:\n"
                    f'{{"position": "top-right", "size_percent": 12, "margin_percent": 2, "reasoning": "reason"}}\n'
                    f"Position options: top-left, top-right, top-center, bottom-left, bottom-right, bottom-center"
                )
            },
            {"type": "image_url", "image_url": {"url": background_url}}
        ]
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            max_tokens=100,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        placement = json.loads(raw.strip())
        logger.info(f"GPT logo placement: {placement}")
        return placement
    except Exception as e:
        logger.info(f"Using smart rules placement (GPT unavailable: {e})")
        return default_placement


def _composite_logo(
    background_bytes: bytes,
    logo_bytes: bytes,
    placement: dict,
    contact_text: str | None = None,
) -> bytes | None:
    """
    Use Pillow to composite logo + contact info onto background image.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        bg = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

        bg_w, bg_h = bg.size
        size_percent = placement.get("size_percent", 20) / 100
        margin_percent = placement.get("margin_percent", 3) / 100
        position = placement.get("position", "top-right")

        # Calculate logo size
        logo_w = int(bg_w * size_percent)
        logo_h = int(logo.height * (logo_w / logo.width))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

        margin = int(bg_w * margin_percent)

        # Calculate position
        if position == "top-left":
            x, y = margin, margin
        elif position == "top-right":
            x, y = bg_w - logo_w - margin, margin
        elif position == "top-center":
            x, y = (bg_w - logo_w) // 2, margin
        elif position == "bottom-left":
            x, y = margin, bg_h - logo_h - margin
        elif position == "bottom-center":
            x, y = (bg_w - logo_w) // 2, bg_h - logo_h - margin
        elif position == "center":
            x, y = (bg_w - logo_w) // 2, (bg_h - logo_h) // 2
        else:  # bottom-right
            x, y = bg_w - logo_w - margin, bg_h - logo_h - margin

        # Paste logo
        bg.paste(logo, (x, y), logo)

        # Add contact text overlay at bottom if provided
        if contact_text:
            draw = ImageDraw.Draw(bg)

            # Try to use a font, fallback to default
            font_size = max(int(bg_w * 0.022), 18)
            try:
                import os
                font_paths = [
                    "C:/Windows/Fonts/arial.ttf",
                    "C:/Windows/Fonts/Arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
                font = None
                for fp in font_paths:
                    if os.path.exists(fp):
                        font = ImageFont.truetype(fp, font_size)
                        break
                if not font:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

            # Draw dark bar at bottom for text
            bar_h = int(bg_h * 0.08)
            bar_y = bg_h - bar_h
            overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [(0, bar_y), (bg_w, bg_h)],
                fill=(0, 0, 0, 180)
            )
            bg = Image.alpha_composite(bg, overlay)
            draw = ImageDraw.Draw(bg)

            # Draw text centered
            try:
                bbox = draw.textbbox((0, 0), contact_text, font=font)
                text_w = bbox[2] - bbox[0]
            except Exception:
                text_w = len(contact_text) * font_size * 0.6

            text_x = (bg_w - text_w) // 2
            text_y = bar_y + (bar_h - font_size) // 2

            # Shadow
            draw.text((text_x + 2, text_y + 2), contact_text, font=font, fill=(0, 0, 0, 255))
            # White text
            draw.text((text_x, text_y), contact_text, font=font, fill=(255, 255, 255, 255))

        final = bg.convert("RGB")
        output = io.BytesIO()
        final.save(output, format="PNG", quality=95)
        return output.getvalue()

    except Exception as e:
        logger.error(f"Logo compositing failed: {e}")
        return None


async def composite_logo_on_image(
    background_url: str,
    logo_url: str,
    prompt: str,
    forced_position: str | None = None,
    contact_text: str | None = None,
    overlay_text: str | None = None,
    overlay_font: str = "Dancing Script",
    overlay_color: str = "#FFFFFF",
) -> str:
    """
    Main function — composites logo on background image intelligently.
    If forced_position is set, skips GPT and uses that position directly.
    Returns URL of final branded image.
    """
    logger.info("Starting logo compositing...")

    bg_bytes, logo_bytes = await asyncio.gather(
        _download_image_bytes(background_url),
        _download_image_bytes(logo_url),
    )

    if not bg_bytes or not logo_bytes:
        logger.error("Failed to download images for compositing")
        return background_url

    if forced_position:
        # User specified position — use it directly with small size
        placement = {
            "position": forced_position,
            "size_percent": 12,  # Small logo
            "margin_percent": 2,
            "reasoning": f"User specified {forced_position}"
        }
        logger.info(f"Using forced position: {forced_position}")
    else:
        # Ask GPT where to place the logo
        placement = await _ask_gpt_logo_placement(background_url, logo_url, prompt)

    final_bytes = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _composite_logo(bg_bytes, logo_bytes, placement, contact_text)
    )

    if not final_bytes:
        logger.error("Compositing failed — returning original")
        return background_url

    filename = f"branded_{uuid.uuid4().hex}.png"
    filepath = IMAGES_DIR / filename
    filepath.write_bytes(final_bytes)

    final_url = f"http://127.0.0.1:8000/static/images/{filename}"
    logger.info(f"Logo composited at {placement['position']}: {filename}")

    # If overlay text also requested — apply it on top of the branded image
    if overlay_text:
        final_url = await add_text_overlay(
            background_url=final_url,
            prompt=prompt,
            overlay_text=overlay_text,
            overlay_font=overlay_font,
            overlay_color=overlay_color,
        )

    return final_url


# Google Fonts download cache
FONTS_DIR = Path("static/fonts")
FONTS_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_FONT_MAP = {
    "Dancing Script": "DancingScript-Bold",
    "Caveat": "Caveat-Bold",
    "Indie Flower": "IndieFlower-Regular",
    "Kalam": "Kalam-Bold",
    "Satisfy": "Satisfy-Regular",
    "Pacifico": "Pacifico-Regular",
    "Sacramento": "Sacramento-Regular",
    "Great Vibes": "GreatVibes-Regular",
    "Allura": "Allura-Regular",
    "Pinyon Script": "PinyonScript-Regular",
    "Playfair Display": "PlayfairDisplay-Bold",
    "Cinzel": "Cinzel-Bold",
    "Tangerine": "Tangerine-Bold",
    "Montserrat": "Montserrat-Bold",
    "Oswald": "Oswald-Bold",
    "Raleway": "Raleway-Bold",
    "Bebas Neue": "BebasNeue-Regular",
    "Anton": "Anton-Regular",
    "Roboto": "Roboto-Bold",
    "Open Sans": "OpenSans-Bold",
    "Lato": "Lato-Bold",
    "Poppins": "Poppins-Bold",
    "Lobster": "Lobster-Regular",
    "Permanent Marker": "PermanentMarker-Regular",
    "Amatic SC": "AmaticSC-Bold",
    "Fredoka One": "FredokaOne-Regular",
}


async def _get_google_font(font_name: str) -> str | None:
    """Get font file path — uses Windows system fonts or downloads TTF."""
    import os

    # Windows system fonts available on all Windows machines
    windows_font_map = {
        "Dancing Script": None,  # Not in Windows
        "Cinzel": None,
        "Pacifico": None,
        "Roboto": None,
        "Poppins": None,
        "Montserrat": None,
        "Oswald": None,
        "Lato": None,
        "Open Sans": None,
        "Nunito": None,
        "Bebas Neue": None,
        "Anton": None,
        "Lobster": None,
        "Permanent Marker": None,
        "Amatic SC": None,
        "Satisfy": None,
        "Great Vibes": None,
        "Tangerine": None,
        "Playfair Display": None,
        "Raleway": None,
        "Fredoka One": None,
        "Righteous": None,
    }

    # Check cached downloaded fonts first
    cache_name = font_name.replace(" ", "_") + ".ttf"
    cache_path = FONTS_DIR / cache_name
    if cache_path.exists():
        return str(cache_path)

    # Font URLs using TTF from reliable sources
    font_urls = {
        "Dancing Script": "https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf",
        "Cinzel": "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
        "Pacifico": "https://raw.githubusercontent.com/google/fonts/main/ofl/pacifico/Pacifico-Regular.ttf",
        "Lobster": "https://raw.githubusercontent.com/google/fonts/main/ofl/lobster/Lobster-Regular.ttf",
        "Oswald": "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
        "Montserrat": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
        "Raleway": "https://raw.githubusercontent.com/google/fonts/main/ofl/raleway/Raleway%5Bwght%5D.ttf",
        "Poppins": "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf",
        "Anton": "https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf",
        "Bebas Neue": "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf",
        "Permanent Marker": "https://raw.githubusercontent.com/google/fonts/main/ofl/permanentmarker/PermanentMarker-Regular.ttf",
        "Amatic SC": "https://raw.githubusercontent.com/google/fonts/main/ofl/amaticsc/AmaticSC-Bold.ttf",
        "Satisfy": "https://raw.githubusercontent.com/google/fonts/main/ofl/satisfy/Satisfy-Regular.ttf",
        "Great Vibes": "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf",
        "Tangerine": "https://raw.githubusercontent.com/google/fonts/main/ofl/tangerine/Tangerine-Bold.ttf",
        "Sacramento": "https://raw.githubusercontent.com/google/fonts/main/ofl/sacramento/Sacramento-Regular.ttf",
        "Roboto": "https://raw.githubusercontent.com/google/fonts/main/apache/roboto/Roboto-Bold.ttf",
        "Lato": "https://raw.githubusercontent.com/google/fonts/main/ofl/lato/Lato-Bold.ttf",
        "Playfair Display": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
        "Fredoka One": "https://raw.githubusercontent.com/google/fonts/main/ofl/fredokaone/FredokaOne-Regular.ttf",
        "Indie Flower": "https://raw.githubusercontent.com/google/fonts/main/ofl/indieflower/IndieFlower-Regular.ttf",
        "Kalam": "https://raw.githubusercontent.com/google/fonts/main/ofl/kalam/Kalam-Bold.ttf",
        "Allura": "https://raw.githubusercontent.com/google/fonts/main/ofl/allura/Allura-Regular.ttf",
        "Libre Baskerville": "https://raw.githubusercontent.com/google/fonts/main/ofl/librebaskerville/LibreBaskerville-Bold.ttf",
        "Nunito": "https://raw.githubusercontent.com/google/fonts/main/ofl/nunito/Nunito%5Bwght%5D.ttf",
        "Open Sans": "https://raw.githubusercontent.com/google/fonts/main/ofl/opensans/OpenSans%5Bwdth%2Cwght%5D.ttf",
        "Righteous": "https://raw.githubusercontent.com/google/fonts/main/ofl/righteous/Righteous-Regular.ttf",
    }

    url = font_urls.get(font_name)
    if not url:
        logger.warning(f"Font '{font_name}' not in map — using system font")
        return None

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
            logger.info(f"Downloaded font: {font_name}")
            return str(cache_path)
    except Exception as e:
        logger.error(f"Font download failed for {font_name}: {e}")
        return None

    # Download font
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
            logger.info(f"Downloaded font: {font_name} → {cache_name}")
            return str(cache_path)
    except Exception as e:
        logger.error(f"Font download failed for {font_name}: {e}")
        return None


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


async def _ask_gpt_text_placement(background_url: str, text: str, prompt: str) -> dict:
    """Decide text placement using smart rules, GPT as enhancement if available."""
    prompt_lower = prompt.lower()

    # Smart rules for text placement
    if any(w in prompt_lower for w in ["villa", "property", "real estate"]):
        default = {"position": "bottom-center", "size_percent": 4, "add_background": True}
    elif any(w in prompt_lower for w in ["product", "bottle", "food"]):
        default = {"position": "bottom-center", "size_percent": 4, "add_background": True}
    elif any(w in prompt_lower for w in ["fashion", "portrait", "person"]):
        default = {"position": "top-center", "size_percent": 4, "add_background": True}
    else:
        default = {"position": "bottom-center", "size_percent": 4, "add_background": True}

    # Try GPT for enhanced placement
    try:
        client = _get_openai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Advertisement for: '{prompt}'\n"
                            f"Add text: '{text}'\n"
                            f"Best position? Respond ONLY with JSON:\n"
                            f'{{"position": "bottom-center", "size_percent": 4, "add_background": true}}\n'
                            f"Positions: top-left, top-center, top-right, bottom-left, bottom-center, bottom-right"
                        )
                    },
                    {"type": "image_url", "image_url": {"url": background_url}}
                ]
            }],
            max_tokens=80,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.info(f"Using smart rules text placement (GPT unavailable)")
        return default


async def add_text_overlay(
    background_url: str,
    prompt: str,
    overlay_text: str,
    overlay_font: str = "Dancing Script",
    overlay_color: str = "#FFFFFF",
) -> str:
    """Add text overlay to image with intelligent GPT placement."""
    bg_bytes = await _download_image_bytes(background_url)
    if not bg_bytes:
        return background_url

    placement = await _ask_gpt_text_placement(background_url, overlay_text, prompt)
    font_path = await _get_google_font(overlay_font)

    def _apply_text(bg_bytes, text, font_path, placement, color_hex):
        try:
            import os
            from PIL import Image, ImageDraw, ImageFont
            bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
            bg_w, bg_h = bg.size
            font_size = max(int(bg_w * placement.get("size_percent", 5) / 100), 20)

            font = None
            if font_path and os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                except Exception:
                    pass
            if not font:
                for fp in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
                    if os.path.exists(fp):
                        try:
                            font = ImageFont.truetype(fp, font_size)
                            break
                        except Exception:
                            pass
            if not font:
                font = ImageFont.load_default()

            position = placement.get("position", "bottom-center")
            add_bg = placement.get("add_background", True)
            margin = int(bg_w * 0.03)

            # Measure text
            temp_draw = ImageDraw.Draw(bg)
            try:
                bbox = temp_draw.textbbox((0, 0), text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except Exception:
                text_w = len(text) * font_size * 0.6
                text_h = font_size

            # Calculate text position
            if "left" in position:
                tx = margin
            elif "right" in position:
                tx = bg_w - int(text_w) - margin
            else:
                tx = (bg_w - int(text_w)) // 2

            if "top" in position:
                ty = margin
            else:
                ty = bg_h - int(text_h) - margin * 2

            # Add background bar if requested
            if add_bg:
                bar_pad = int(font_size * 0.5)
                overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
                ImageDraw.Draw(overlay).rectangle(
                    [(tx - bar_pad, ty - bar_pad), (tx + int(text_w) + bar_pad, ty + int(text_h) + bar_pad)],
                    fill=(0, 0, 0, 160)
                )
                bg = Image.alpha_composite(bg, overlay)

            draw = ImageDraw.Draw(bg)
            rgb = _hex_to_rgb(color_hex)

            # Shadow
            draw.text((tx + 2, ty + 2), text, font=font, fill=(0, 0, 0, 200))
            # Main text
            draw.text((tx, ty), text, font=font, fill=(*rgb, 255))

            out = io.BytesIO()
            bg.convert("RGB").save(out, format="PNG", quality=95)
            return out.getvalue()
        except Exception as e:
            logger.error(f"Text overlay failed: {e}")
            return None

    final_bytes = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _apply_text(bg_bytes, overlay_text, font_path, placement, overlay_color)
    )

    if not final_bytes:
        return background_url

    filename = f"text_{uuid.uuid4().hex}.png"
    (IMAGES_DIR / filename).write_bytes(final_bytes)
    logger.info(f"Text overlay added: {filename}")
    return f"http://127.0.0.1:8000/static/images/{filename}"
