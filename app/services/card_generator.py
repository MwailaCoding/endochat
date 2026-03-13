"""Card generator service for shareable answer cards."""

import io
import hashlib
import secrets
from typing import Optional
from pathlib import Path

import httpx
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

from app.config import settings
from app.services.storage.cloudinary_client import CloudinaryClient
from app.services.utils.logging import get_logger
from app.core.exceptions import EndoChatException

logger = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "cards"


class CardGeneratorError(EndoChatException):
    """Card generation error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message=message, detail=detail, error_code="CARD_GENERATION_ERROR")


class CardGenerator:
    """Service for generating shareable answer cards."""

    def __init__(
        self,
        cloudinary_client: Optional[CloudinaryClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        """Initialize the card generator."""
        self.cloudinary = cloudinary_client or CloudinaryClient()
        self.http_client = http_client
        self._own_client = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)
            self._own_client = True
        return self.http_client

    async def close(self):
        """Close HTTP client if we own it."""
        if self._own_client and self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    def generate_tracking_code(self, length: int = 8) -> str:
        """Generate a unique tracking code."""
        return secrets.token_urlsafe(length)[:length]

    def _load_template(self, template_name: str) -> str:
        """Load an HTML template from the templates directory."""
        template_path = TEMPLATES_DIR / template_name
        if not template_path.exists():
            raise CardGeneratorError(
                message=f"Template not found: {template_name}",
                detail=f"Expected template at {template_path}",
            )
        return template_path.read_text(encoding="utf-8")

    def _render_template(self, template: str, **kwargs) -> str:
        """Render template with variables."""
        for key, value in kwargs.items():
            placeholder = f"{{{{{key}}}}}"
            template = template.replace(placeholder, str(value) if value else "")
        return template

    async def generate_qr_code(self, url: str, size: int = 200) -> bytes:
        """
        Generate a QR code image.

        Args:
            url: URL to encode
            size: Size of the QR code in pixels

        Returns:
            PNG image bytes
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            fill_color="#F59E0B",
            back_color="white",
        )

        img_resized = img.resize((size, size))
        buffer = io.BytesIO()
        img_resized.save(buffer, format="PNG")
        return buffer.getvalue()

    async def html_to_image(self, html: str, css: str = "") -> bytes:
        """
        Convert HTML to an image using the HTML-to-Image API.

        Args:
            html: HTML content
            css: Optional CSS styles

        Returns:
            Image bytes
        """
        if not settings.is_hcti_available:
            raise CardGeneratorError(
                message="HTML-to-Image API not configured",
                detail="Set HCTI_API_USER_ID and HCTI_API_KEY in environment",
            )

        client = await self._get_http_client()

        try:
            response = await client.post(
                "https://hcti.io/v1/image",
                auth=(settings.hcti_api_user_id, settings.hcti_api_key),
                json={
                    "html": html,
                    "css": css,
                    "google_fonts": "Inter",
                },
            )
            response.raise_for_status()

            result = response.json()
            image_url = result.get("url")

            if not image_url:
                raise CardGeneratorError(
                    message="No image URL returned from API",
                    detail=str(result),
                )

            image_response = await client.get(image_url)
            image_response.raise_for_status()
            return image_response.content

        except httpx.HTTPStatusError as e:
            logger.error("HTML-to-Image API error", status=e.response.status_code)
            raise CardGeneratorError(
                message="Failed to generate image",
                detail=f"API returned status {e.response.status_code}",
            )
        except Exception as e:
            logger.error("HTML-to-Image conversion failed", error=str(e))
            raise CardGeneratorError(
                message="Failed to convert HTML to image",
                detail=str(e),
            )

    async def generate_fact_card(
        self,
        title: str,
        content: str,
        source: Optional[str] = None,
        share_url: Optional[str] = None,
    ) -> dict:
        """
        Generate a fact card image.

        Args:
            title: Card title
            content: Main content/fact
            source: Source citation
            share_url: URL for QR code

        Returns:
            dict with image_url, qr_code_url, tracking_code
        """
        tracking_code = self.generate_tracking_code()

        html = self._load_template("fact_card.html")
        html = self._render_template(
            html,
            title=title,
            content=content,
            source=source or "",
            url=share_url or "",
        )

        image_bytes = await self.html_to_image(html)

        upload_result = await self.cloudinary.upload_image(
            image_bytes,
            folder="endochat/cards",
            public_id=f"fact_{tracking_code}",
        )

        qr_result = None
        if share_url:
            qr_bytes = await self.generate_qr_code(share_url)
            qr_result = await self.cloudinary.upload_image(
                qr_bytes,
                folder="endochat/qr",
                public_id=f"qr_{tracking_code}",
            )

        return {
            "image_url": upload_result["url"],
            "qr_code_url": qr_result["url"] if qr_result else None,
            "tracking_code": tracking_code,
            "card_type": "fact",
        }

    async def generate_stat_card(
        self,
        stat_value: str,
        stat_label: str,
        description: str,
        source: Optional[str] = None,
        share_url: Optional[str] = None,
    ) -> dict:
        """
        Generate a statistic card image.

        Args:
            stat_value: The main statistic (e.g., "10%", "1 in 10")
            stat_label: Label for the stat
            description: Additional description
            source: Source citation
            share_url: URL for QR code

        Returns:
            dict with image_url, qr_code_url, tracking_code
        """
        tracking_code = self.generate_tracking_code()

        html = self._load_template("stat_card.html")
        html = self._render_template(
            html,
            stat_value=stat_value,
            stat_label=stat_label,
            description=description,
            source=source or "",
            url=share_url or "",
        )

        image_bytes = await self.html_to_image(html)

        upload_result = await self.cloudinary.upload_image(
            image_bytes,
            folder="endochat/cards",
            public_id=f"stat_{tracking_code}",
        )

        qr_result = None
        if share_url:
            qr_bytes = await self.generate_qr_code(share_url)
            qr_result = await self.cloudinary.upload_image(
                qr_bytes,
                folder="endochat/qr",
                public_id=f"qr_{tracking_code}",
            )

        return {
            "image_url": upload_result["url"],
            "qr_code_url": qr_result["url"] if qr_result else None,
            "tracking_code": tracking_code,
            "card_type": "stat",
        }

    async def generate_candle_card(
        self,
        candle_count: int,
        message: Optional[str] = None,
        share_url: Optional[str] = None,
    ) -> dict:
        """
        Generate a candle ceremony card.

        Args:
            candle_count: Total candles lit
            message: Optional dedication message
            share_url: URL for QR code

        Returns:
            dict with image_url, qr_code_url, tracking_code
        """
        tracking_code = self.generate_tracking_code()

        html = self._load_template("candle_card.html")
        html = self._render_template(
            html,
            candle_count=f"{candle_count:,}",
            message=message or "Light a candle for endometriosis awareness",
            url=share_url or "",
        )

        image_bytes = await self.html_to_image(html)

        upload_result = await self.cloudinary.upload_image(
            image_bytes,
            folder="endochat/cards",
            public_id=f"candle_{tracking_code}",
        )

        qr_result = None
        if share_url:
            qr_bytes = await self.generate_qr_code(share_url)
            qr_result = await self.cloudinary.upload_image(
                qr_bytes,
                folder="endochat/qr",
                public_id=f"qr_{tracking_code}",
            )

        return {
            "image_url": upload_result["url"],
            "qr_code_url": qr_result["url"] if qr_result else None,
            "tracking_code": tracking_code,
            "card_type": "candle",
        }
