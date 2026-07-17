from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, Request
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

_READ_CHUNK_SIZE = 64 * 1024
_MAX_BOUNDARY_BYTES = 200
_MAX_CONTEXT_BYTES = 100
_MAX_PART_HEADERS = 8
_MAX_HEADER_NAME_BYTES = 100
_MAX_HEADER_VALUE_BYTES = 4096


@dataclass(frozen=True)
class ParsedUpload:
    context: str
    content_type: str
    file_path: Path
    size_bytes: int


def validate_content_length(request: Request, max_upload_bytes: int) -> None:
    values = [
        value.decode("latin-1")
        for name, value in request.scope.get("headers", [])
        if name.lower() == b"content-length"
    ]
    if not values:
        return
    if len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
        raise HTTPException(status_code=400, detail="invalid content-length")
    if int(values[0]) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="upload is too large")


async def stream_request_to_file(request: Request, target: BinaryIO, max_upload_bytes: int) -> int:
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_upload_bytes:
            raise HTTPException(status_code=413, detail="upload is too large")
        target.write(chunk)
    target.flush()
    if total == 0:
        raise HTTPException(status_code=422, detail="empty upload")
    return total


def parse_multipart_upload(
    source: BinaryIO,
    target_path: Path,
    content_type_header: str | None,
    max_image_bytes: int,
) -> ParsedUpload:
    media_type, options = parse_options_header(content_type_header)
    boundary = options.get(b"boundary")
    if (
        media_type.lower() != b"multipart/form-data"
        or boundary is None
        or not boundary
        or len(boundary) > _MAX_BOUNDARY_BYTES
    ):
        raise HTTPException(status_code=400, detail="invalid multipart upload")

    header_name = bytearray()
    header_value = bytearray()
    headers: dict[bytes, bytes] = {}
    part_name: bytes | None = None
    part_content_type: bytes | None = None
    file_content_type: bytes | None = None
    context_bytes = bytearray()
    file_handle: BinaryIO | None = None
    file_size = 0
    found_context = False
    found_file = False
    complete = False
    header_count = 0

    def on_part_begin() -> None:
        nonlocal headers, part_name, part_content_type, header_count
        headers = {}
        part_name = None
        part_content_type = None
        header_count = 0
        header_name.clear()
        header_value.clear()

    def on_header_field(data: bytes, start: int, end: int) -> None:
        if len(header_name) + end - start > _MAX_HEADER_NAME_BYTES:
            raise ValueError("header name too large")
        header_name.extend(data[start:end])

    def on_header_value(data: bytes, start: int, end: int) -> None:
        if len(header_value) + end - start > _MAX_HEADER_VALUE_BYTES:
            raise ValueError("header value too large")
        header_value.extend(data[start:end])

    def on_header_end() -> None:
        nonlocal header_count
        header_count += 1
        if header_count > _MAX_PART_HEADERS:
            raise ValueError("too many part headers")
        headers[bytes(header_name).lower()] = bytes(header_value)
        header_name.clear()
        header_value.clear()

    def on_headers_finished() -> None:
        nonlocal part_name, part_content_type, file_content_type
        nonlocal file_handle, found_context, found_file
        disposition, disposition_options = parse_options_header(headers.get(b"content-disposition"))
        if disposition.lower() != b"form-data":
            raise ValueError("invalid disposition")
        part_name = disposition_options.get(b"name")
        part_content_type = headers.get(b"content-type")
        if part_name == b"context":
            if found_context:
                raise ValueError("duplicate context")
            found_context = True
        elif part_name == b"file":
            if found_file or b"filename" not in disposition_options:
                raise ValueError("invalid file part")
            found_file = True
            file_content_type = part_content_type
            file_handle = target_path.open("xb")
        else:
            raise ValueError("unexpected part")

    def on_part_data(data: bytes, start: int, end: int) -> None:
        nonlocal file_size
        chunk = data[start:end]
        if part_name == b"context":
            if len(context_bytes) + len(chunk) > _MAX_CONTEXT_BYTES:
                raise ValueError("context too large")
            context_bytes.extend(chunk)
        elif part_name == b"file" and file_handle is not None:
            file_size += len(chunk)
            if file_size > max_image_bytes:
                raise HTTPException(status_code=413, detail="image is too large")
            file_handle.write(chunk)

    def on_part_end() -> None:
        nonlocal file_handle
        if file_handle is not None:
            file_handle.close()
            file_handle = None

    def on_end() -> None:
        nonlocal complete
        complete = True

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
            "on_part_end": on_part_end,
            "on_end": on_end,
        },
        max_header_count=_MAX_PART_HEADERS,
        max_header_size=_MAX_HEADER_NAME_BYTES + _MAX_HEADER_VALUE_BYTES + 2,
    )
    try:
        source.seek(0)
        while chunk := source.read(_READ_CHUNK_SIZE):
            parser.write(chunk)
        parser.finalize()
    except HTTPException:
        raise
    except (MultipartParseError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid multipart upload") from exc
    finally:
        if file_handle is not None:
            file_handle.close()

    if not complete or not found_context or not found_file:
        raise HTTPException(status_code=400, detail="invalid multipart upload")
    if file_size == 0:
        raise HTTPException(status_code=422, detail="empty image")
    try:
        context = context_bytes.decode("utf-8")
        content_type = (file_content_type or b"application/octet-stream").decode("ascii")
    except UnicodeError as exc:
        raise HTTPException(status_code=400, detail="invalid multipart upload") from exc
    return ParsedUpload(
        context=context,
        content_type=content_type,
        file_path=target_path,
        size_bytes=file_size,
    )
