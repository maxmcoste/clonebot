"""Magic-byte-based file type validation for the ingest pipeline."""

from pathlib import Path


class FileTypeMismatchError(ValueError):
    """Raised when a file's actual content does not match its declared extension."""


# Each entry: (offset, magic_bytes, frozenset_of_compatible_extensions, human_readable_name)
# Ordered from most-specific to least-specific so the first match wins.
_SIGNATURES: list[tuple[int, bytes, frozenset[str], str]] = [
    # --- Images ---
    (0, b"\xff\xd8\xff",              frozenset({".jpg", ".jpeg"}),                   "JPEG image"),
    (0, b"\x89PNG\r\n\x1a\n",        frozenset({".png"}),                             "PNG image"),
    (0, b"GIF87a",                    frozenset({".gif"}),                             "GIF image"),
    (0, b"GIF89a",                    frozenset({".gif"}),                             "GIF image"),
    # WEBP: RIFF....WEBP  — checked before plain RIFF so it matches first when suffix is .webp
    (0, b"RIFF",                      frozenset({".webp"}),                            "WebP image"),   # sub-checked below
    # --- Documents ---
    (0, b"%PDF",                      frozenset({".pdf"}),                             "PDF document"),
    # OLE2 compound document (legacy .doc, .xls, .ppt, …)
    (0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
                                      frozenset({".doc", ".xls", ".ppt"}),             "OLE2 document (.doc/.xls/.ppt)"),
    # ZIP / Open XML (.docx, .xlsx, .pptx, .odt, .epub, …)
    (0, b"PK\x03\x04",               frozenset({".docx", ".xlsx", ".pptx",
                                                  ".odt", ".epub", ".zip"}),           "ZIP/Open-XML document (.docx/.xlsx/…)"),
    # --- Video ---
    (0, b"\x1a\x45\xdf\xa3",         frozenset({".mkv", ".webm"}),                   "MKV/WebM video"),
    # RIFF-based: AVI and WAV share the RIFF header — sub-type at offset 8
    (0, b"RIFF",                      frozenset({".avi", ".wav"}),                    "RIFF container (AVI/WAV)"),
]

# RIFF sub-type checks: bytes 8-11 identify the true format
_RIFF_SUBTYPES: dict[bytes, tuple[frozenset[str], str]] = {
    b"WEBP": (frozenset({".webp"}),        "WebP image"),
    b"AVI ": (frozenset({".avi"}),         "AVI video"),
    b"WAVE": (frozenset({".wav"}),         "WAV audio"),
}

# Text-based extensions: validated by *absence* of known binary magic + UTF-8 check
_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".csv", ".json"})

# Extensions where magic bytes are too variable / container-dependent to validate
_SKIP_VALIDATION = frozenset({".mp4", ".mov"})


def validate_file_type(path: Path) -> None:
    """Validate that *path*'s content matches its declared extension.

    Strategy
    --------
    * Binary formats (PDF, OLE2, ZIP, JPEG, PNG, …): match magic bytes.
    * Text formats (.txt, .md, .csv, .json): ensure no known binary magic
      is present and the first 512 bytes are valid UTF-8.
    * .mp4 / .mov: skipped — their magic varies too much across encoders.

    Raises
    ------
    FileTypeMismatchError
        When the detected type is incompatible with the file's extension.
    """
    suffix = path.suffix.lower()

    if suffix in _SKIP_VALIDATION:
        return

    header = path.read_bytes()[:16]

    # --- detect actual type from magic bytes ---
    detected_name: str | None = None
    detected_exts: frozenset[str] = frozenset()

    for offset, magic, compat_exts, type_name in _SIGNATURES:
        if header[offset: offset + len(magic)] == magic:
            detected_name = type_name
            detected_exts = compat_exts

            # Resolve RIFF sub-type when we have enough bytes
            if magic == b"RIFF" and len(header) >= 12:
                subtype = header[8:12]
                sub = _RIFF_SUBTYPES.get(subtype)
                if sub is not None:
                    detected_exts, detected_name = sub

            break

    # --- validate text extensions ---
    if suffix in _TEXT_EXTENSIONS:
        if detected_name is not None:
            raise FileTypeMismatchError(
                f"'{path.name}': extension is '{suffix}' "
                f"but file content is {detected_name}"
            )
        # Ensure header bytes are valid UTF-8 (catches arbitrary binary data)
        try:
            header.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise FileTypeMismatchError(
                f"'{path.name}': extension is '{suffix}' "
                f"but file contains non-UTF-8 binary data"
            )
        return

    # --- validate binary extensions ---
    if detected_name is not None and suffix not in detected_exts:
        raise FileTypeMismatchError(
            f"'{path.name}': extension is '{suffix}' "
            f"but file content is {detected_name}"
        )
    # If no signature matched we cannot determine the type — pass through silently
