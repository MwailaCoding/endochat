"""Cloudinary client for image storage."""

import io
from typing import Optional
from datetime import datetime

import cloudinary
import cloudinary.uploader
import cloudinary.api

from app.config import settings
from app.services.utils.logging import get_logger
from app.core.exceptions import EndoChatException

logger = get_logger(__name__)


class CloudinaryError(EndoChatException):
    """Cloudinary-specific error."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message=message, detail=detail, error_code="CLOUDINARY_ERROR")


class CloudinaryClient:
    """Client for Cloudinary image storage operations."""

    def __init__(self):
        """Initialize Cloudinary with credentials."""
        self._configured = False
        if settings.is_cloudinary_available:
            cloudinary.config(
                cloud_name=settings.cloudinary_cloud_name,
                api_key=settings.cloudinary_api_key,
                api_secret=settings.cloudinary_api_secret,
                secure=True,
            )
            self._configured = True
            logger.info("Cloudinary client initialized")
        else:
            logger.warning("Cloudinary not configured - image upload will be disabled")

    @property
    def is_available(self) -> bool:
        """Check if Cloudinary is configured."""
        return self._configured

    async def upload_image(
        self,
        image_data: bytes,
        folder: str = "endochat",
        public_id: Optional[str] = None,
        resource_type: str = "image",
        transformation: Optional[dict] = None,
    ) -> dict:
        """
        Upload an image to Cloudinary.

        Args:
            image_data: Raw image bytes
            folder: Folder path in Cloudinary
            public_id: Optional custom public ID
            resource_type: Type of resource (image, video, raw)
            transformation: Optional transformations to apply

        Returns:
            dict with upload result including url, secure_url, public_id
        """
        if not self._configured:
            raise CloudinaryError(
                message="Cloudinary not configured",
                detail="Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET",
            )

        try:
            upload_options = {
                "folder": folder,
                "resource_type": resource_type,
            }

            if public_id:
                upload_options["public_id"] = public_id

            if transformation:
                upload_options["transformation"] = transformation

            result = cloudinary.uploader.upload(
                io.BytesIO(image_data),
                **upload_options,
            )

            logger.info(
                "Image uploaded to Cloudinary",
                public_id=result.get("public_id"),
                url=result.get("secure_url"),
            )

            return {
                "url": result.get("secure_url"),
                "public_id": result.get("public_id"),
                "width": result.get("width"),
                "height": result.get("height"),
                "format": result.get("format"),
                "bytes": result.get("bytes"),
                "created_at": result.get("created_at"),
            }

        except cloudinary.exceptions.Error as e:
            logger.error("Cloudinary upload failed", error=str(e))
            raise CloudinaryError(
                message="Failed to upload image",
                detail=str(e),
            )

    async def upload_from_url(
        self,
        url: str,
        folder: str = "endochat",
        public_id: Optional[str] = None,
    ) -> dict:
        """
        Upload an image from a URL to Cloudinary.

        Args:
            url: Source image URL
            folder: Folder path in Cloudinary
            public_id: Optional custom public ID

        Returns:
            dict with upload result
        """
        if not self._configured:
            raise CloudinaryError(
                message="Cloudinary not configured",
                detail="Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET",
            )

        try:
            upload_options = {
                "folder": folder,
            }

            if public_id:
                upload_options["public_id"] = public_id

            result = cloudinary.uploader.upload(url, **upload_options)

            logger.info(
                "Image uploaded from URL to Cloudinary",
                source_url=url,
                public_id=result.get("public_id"),
            )

            return {
                "url": result.get("secure_url"),
                "public_id": result.get("public_id"),
                "width": result.get("width"),
                "height": result.get("height"),
                "format": result.get("format"),
            }

        except cloudinary.exceptions.Error as e:
            logger.error("Cloudinary upload from URL failed", error=str(e), url=url)
            raise CloudinaryError(
                message="Failed to upload image from URL",
                detail=str(e),
            )

    async def delete_image(self, public_id: str) -> bool:
        """
        Delete an image from Cloudinary.

        Args:
            public_id: The public ID of the image to delete

        Returns:
            True if deletion was successful
        """
        if not self._configured:
            return False

        try:
            result = cloudinary.uploader.destroy(public_id)
            success = result.get("result") == "ok"

            if success:
                logger.info("Image deleted from Cloudinary", public_id=public_id)
            else:
                logger.warning(
                    "Image deletion returned unexpected result",
                    public_id=public_id,
                    result=result,
                )

            return success

        except cloudinary.exceptions.Error as e:
            logger.error("Cloudinary deletion failed", error=str(e), public_id=public_id)
            return False

    def get_url(
        self,
        public_id: str,
        transformation: Optional[dict] = None,
        format: str = "png",
    ) -> str:
        """
        Generate a URL for an existing Cloudinary image.

        Args:
            public_id: The public ID of the image
            transformation: Optional transformations
            format: Output format

        Returns:
            The generated URL
        """
        options = {"format": format}

        if transformation:
            options["transformation"] = transformation

        return cloudinary.CloudinaryImage(public_id).build_url(**options)

    async def create_share_image_url(
        self,
        public_id: str,
        width: int = 1200,
        height: int = 630,
    ) -> str:
        """
        Generate an optimized URL for social sharing.

        Args:
            public_id: The public ID of the image
            width: Target width (default 1200 for Open Graph)
            height: Target height (default 630 for Open Graph)

        Returns:
            Optimized URL for social sharing
        """
        return cloudinary.CloudinaryImage(public_id).build_url(
            transformation=[
                {"width": width, "height": height, "crop": "fill"},
                {"quality": "auto", "fetch_format": "auto"},
            ]
        )
