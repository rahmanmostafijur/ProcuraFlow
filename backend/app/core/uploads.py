import io
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

READ_CHUNK_BYTES = 64 * 1024
# Logos are shown small and embedded in PDFs; a larger canvas only costs memory.
MAX_LOGO_PIXELS = 4096 * 4096

# Pillow format name -> (content type served back, file extension used in the storage key).
IMAGE_FORMATS = {"PNG": ("image/png", "png"), "JPEG": ("image/jpeg", "jpg")}


@dataclass(frozen=True)
class ValidatedFile:
    data: bytes
    content_type: str
    extension: str


async def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an upload, refusing it as soon as it passes ``max_bytes`` rather than after buffering all of it."""
    chunks: list[bytes] = []
    size = 0
    while chunk := await upload.read(READ_CHUNK_BYTES):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"The file is larger than the {max_bytes // 1024} KB limit.",
            )
        chunks.append(chunk)
    if size == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The file is empty.")
    return b"".join(chunks)


def validate_image(data: bytes, allowed_formats: frozenset[str] = frozenset(IMAGE_FORMATS)) -> ValidatedFile:
    """Accept the bytes only if they decode as an allowed image format; the client's content type is ignored."""
    unsupported = HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Upload a {' or '.join(sorted(allowed_formats))} image.",
    )
    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise unsupported from exc

    if image_format not in allowed_formats:
        raise unsupported
    if width * height > MAX_LOGO_PIXELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The image is too large; use one under 4096 x 4096 pixels.",
        )
    content_type, extension = IMAGE_FORMATS[image_format]
    return ValidatedFile(data=data, content_type=content_type, extension=extension)
