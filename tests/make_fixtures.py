#!/usr/bin/env python3
"""Generate the CBZ archives used to test index.html.

Uses only the Python standard library. See tests/README.md for what each
archive should do when opened in the viewer.
"""

import argparse
import base64
import io
import struct
import zipfile
import zlib
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).parent / "fixtures"

# A plain ZIP count field tops out at 65,535 entries
ZIP_ENTRY_LIMIT = 0xFFFF
# Puts pages past the point where ZIP needs 64-bit offsets (4 GiB)
LARGE_OFFSET = 4 * 1024**3 + 64 * 1024**2

# A 1x1 lossless WebP image
WEBP_PAGE = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")

LOCAL_HEADER_SIZE = 30


def png(color, width=400, height=600):
    """Return a solid-color PNG, so that each page is visibly different."""

    def chunk(kind, data):
        checksum = zlib.crc32(kind + data)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(color) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


RED = png((200, 40, 40))
GREEN = png((40, 160, 70))
BLUE = png((40, 70, 200))
PAGES = {"page01.png": RED, "page02.png": GREEN, "page03.png": BLUE}


def write_entries(target, entries, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(target, "w", compression) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def build(entries, compression=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    write_entries(buffer, entries, compression)
    return bytearray(buffer.getvalue())


def eocd_position(data):
    return data.rfind(b"PK\x05\x06")


def central_directory_offset(data, name):
    """Return the offset of the central directory entry for `name`."""
    position = struct.unpack_from("<I", data, eocd_position(data) + 16)[0]
    while data[position : position + 4] == b"PK\x01\x02":
        name_length, extra_length, comment_length = struct.unpack_from("<HHH", data, position + 28)
        if data[position + 46 : position + 46 + name_length].decode() == name:
            return position
        position += 46 + name_length + extra_length + comment_length
    raise KeyError(name)


def local_header_offset(data, name):
    return struct.unpack_from("<I", data, central_directory_offset(data, name) + 42)[0]


def mark_encrypted(data, name):
    """Set the encryption flag on an entry, in both of its headers."""
    data[local_header_offset(data, name) + 6] |= 1
    data[central_directory_offset(data, name) + 8] |= 1


def corrupt_compressed_data(data, name):
    """Overwrite an entry's data with bytes that are not a valid deflate stream."""
    central = central_directory_offset(data, name)
    compressed_size = struct.unpack_from("<I", data, central + 20)[0]
    local = local_header_offset(data, name)
    name_length, extra_length = struct.unpack_from("<HH", data, local + 26)
    start = local + LOCAL_HEADER_SIZE + name_length + extra_length
    data[start : start + compressed_size] = b"\xff" * compressed_size


# --- Archives that should load completely ---


def basic(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("page01.png", RED, zipfile.ZIP_STORED)
        archive.writestr("page02.png", GREEN, zipfile.ZIP_DEFLATED)
        archive.writestr("page03.png", BLUE, zipfile.ZIP_DEFLATED)


def webp(path):
    write_entries(path, {**PAGES, "page04.webp": WEBP_PAGE})


def data_descriptors(path):
    """Write sizes after each entry, leaving them as zero in the local headers."""

    class Unseekable:
        def __init__(self, stream):
            self.stream = stream

        def write(self, data):
            return self.stream.write(data)

        def flush(self):
            self.stream.flush()

    with open(path, "wb") as stream:
        write_entries(Unseekable(stream), PAGES)


def macos_metadata(path):
    write_entries(
        path,
        {
            **PAGES,
            "__MACOSX/page01.png": b"metadata",
            "__MACOSX/._page01.png": b"metadata",
            "._page02.png": b"metadata",
        },
    )


def short_book(path):
    """Use pages small enough for the whole book to fit on screen."""
    write_entries(
        path,
        {
            "page01.png": png((200, 40, 40), height=150),
            "page02.png": png((40, 160, 70), height=150),
        },
    )


def large_book(path):
    """Use enough pages to take a few seconds to load."""
    colors = ((200, 40, 40), (40, 160, 70), (40, 70, 200))
    images = [png(color, width=1000, height=1500) for color in colors]
    write_entries(path, {f"page{index:03}.png": images[index % 3] for index in range(400)})


def unpadded_names(path):
    """Store pages out of order, with names that only sort correctly as numbers."""
    write_entries(
        path,
        {
            "page10.png": png((40, 70, 200), width=500),
            "page2.png": png((40, 160, 70), width=450),
            "page1.png": png((200, 40, 40), width=400),
        },
    )


def _many_entries(path, filler_count):
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(filler_count):
            archive.writestr(f"metadata/{index:05}.txt", b"")
        for name, data in PAGES.items():
            archive.writestr(name, data)


def exactly_65535_entries(path):
    """Use the highest count a plain ZIP can hold, with no ZIP64 records."""
    _many_entries(path, ZIP_ENTRY_LIMIT - len(PAGES))


def zip64_many_entries(path):
    """Exceed the plain ZIP entry limit, which forces ZIP64 end records."""
    _many_entries(path, ZIP_ENTRY_LIMIT + 1)


def zip64_large_offset(path):
    """Put pages past 4 GiB, which forces ZIP64 offsets on each entry.

    The space before the pages is a sparse hole, so on most file systems the
    archive only uses a few kilobytes of disk despite its reported size.
    """
    with open(path, "wb") as stream:
        stream.truncate(LARGE_OFFSET)
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as archive:
        for name, data in PAGES.items():
            archive.writestr(name, data)


# --- Archives that should load with a warning ---


def corrupt_page(path):
    data = build(PAGES)
    corrupt_compressed_data(data, "page02.png")
    path.write_bytes(data)


def undecodable_page(path):
    write_entries(path, {**PAGES, "page02.png": b"this is not an image"})


def partly_encrypted(path):
    data = build(PAGES)
    mark_encrypted(data, "page02.png")
    path.write_bytes(data)


def unsupported_compression(path):
    data = build(PAGES)
    # Method 12 is bzip2, which the viewer doesn't support
    data[central_directory_offset(data, "page02.png") + 10] = 12
    path.write_bytes(data)


# --- Archives that should fail with an error message ---


def not_a_zip(path):
    path.write_bytes(b"7z\xbc\xaf\x27\x1c" + bytes(range(256)) * 8)


def truncated(path):
    data = build(PAGES)
    path.write_bytes(data[: len(data) // 2])


def no_images(path):
    write_entries(path, {"readme.txt": b"no pages here", "info.xml": b"<info/>"})


def all_encrypted(path):
    data = build(PAGES)
    for name in PAGES:
        mark_encrypted(data, name)
    path.write_bytes(data)


def all_pages_corrupt(path):
    data = build(PAGES)
    for name in PAGES:
        corrupt_compressed_data(data, name)
    path.write_bytes(data)


def bad_central_directory(path):
    data = build(PAGES)
    data[central_directory_offset(data, "page02.png")] = 0
    path.write_bytes(data)


def truncated_central_directory(path):
    """Report a central directory too small to hold its first entry."""
    data = build(PAGES)
    struct.pack_into("<I", data, eocd_position(data) + 12, 10)
    path.write_bytes(data)


def zip64_missing_records(path):
    data = build(PAGES)
    struct.pack_into("<I", data, eocd_position(data) + 16, 0xFFFFFFFF)
    path.write_bytes(data)


def zip64_invalid_record(path):
    """Add a ZIP64 locator that points at something other than a ZIP64 record."""
    data = build(PAGES)
    eocd = eocd_position(data)
    struct.pack_into("<I", data, eocd + 16, 0xFFFFFFFF)
    locator = struct.pack("<IIQI", 0x07064B50, 0, 0, 1)
    path.write_bytes(data[:eocd] + locator + data[eocd:])


FIXTURES = {
    "basic": basic,
    "webp": webp,
    "data-descriptors": data_descriptors,
    "macos-metadata": macos_metadata,
    "unpadded-names": unpadded_names,
    "short-book": short_book,
    "large-book": large_book,
    "exactly-65535-entries": exactly_65535_entries,
    "zip64-many-entries": zip64_many_entries,
    "zip64-large-offset": zip64_large_offset,
    "corrupt-page": corrupt_page,
    "undecodable-page": undecodable_page,
    "partly-encrypted": partly_encrypted,
    "unsupported-compression": unsupported_compression,
    "not-a-zip": not_a_zip,
    "truncated": truncated,
    "no-images": no_images,
    "all-encrypted": all_encrypted,
    "all-pages-corrupt": all_pages_corrupt,
    "bad-central-directory": bad_central_directory,
    "truncated-central-directory": truncated_central_directory,
    "zip64-missing-records": zip64_missing_records,
    "zip64-invalid-record": zip64_invalid_record,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="directory to write the archives to (default: tests/fixtures)",
    )
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)

    for name, create in FIXTURES.items():
        path = output / f"{name}.cbz"
        path.unlink(missing_ok=True)
        create(path)
        print(f"{path}  ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
