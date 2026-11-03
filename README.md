# cbz-viewer

A client-side viewer for CBZ comic and manga archives, delivered as a single HTML file.

Files are read and decoded locally in the browser and are never uploaded. The application has no backend, build step, or third-party dependencies.

This project is a fork of [HtmlCbz](https://github.com/MaxAdams0/HtmlCbz) by MaxAdams0.

## Features

- Opens ZIP-based `.cbz` archives through the browser's file picker, including large ZIP64 archives
- Displays pages in a continuous vertical scroll
- Tracks the current page as you scroll
- Adjusts page size from 25% to 250%, staying on the current page
- Supports JPEG, PNG, GIF, and WebP pages
- Skips pages that can't be loaded, and reports how many were skipped

## Getting started

### Run locally

Clone the repository and open `index.html` in a browser:

```sh
git clone git@github.com:Szerl0k/cbz-viewer.git
cd cbz-viewer
xdg-open index.html   # Linux; use `open` on macOS or `start` on Windows
```

### Deploy

`index.html` is the only file the application needs. To deploy it, publish that file to any static host, such as GitHub Pages or Cloudflare Pages.

### Browser requirements

The browser must support the [`DecompressionStream`](https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream) API with the `deflate-raw` format.

## Usage

1. Choose a `.cbz` file with the file picker in the bottom toolbar.
2. Scroll to read. The page counter is at the right of the toolbar.
3. Change the page size with the zoom slider or number field. At 100%, a page fits the area above the toolbar without growing past its natural size. Press Enter to apply a typed value.

## How it works

All of the application code is in `index.html`. The ZIP parsing functions take a `File` and return data without touching the page, which keeps them separate from page loading and display. A book opens in these steps:

1. **Reading:** the archive is never loaded into memory as a whole. `File.slice()` reads only the parts needed at each step.
2. **Parsing:** a built-in ZIP parser finds the archive's end-of-central-directory record, using the ZIP64 records when present, then reads each entry's name, compression method, size, and data offset from the central directory.
3. **Page selection:** entries with a supported image extension are kept and sorted by filename in natural order, so `page2` comes before `page10`. macOS metadata files are left out.
4. **Decompression:** stored entries are used directly as file slices, and deflated entries are streamed through the native `DecompressionStream` API.
5. **Rendering:** each page becomes a `Blob`, exposed through an object URL and displayed as an `<img>` element.
6. **Navigation:** cumulative page heights are used to work out the current page and to restore the scroll position after a zoom change or window resize.

## Known limitations

- Only ZIP-based archives are supported, not RAR or 7z. Encrypted archives are also unsupported.
- Image formats not listed under [Features](#features) are ignored.
- Every page is processed before the book is ready, so large archives take longer to open and can still use a lot of memory.

## Testing

The project has no automated test suite. [`tests/README.md`](tests/README.md) explains how to generate the test archives and check them in a browser.

## To do

Known problems in `index.html`.

### Bugs

- [ ] **Valid archives can be rejected (`findEocdPosition`).** The search for the end-of-central-directory record takes the last signature match without checking the comment length. If an archive's comment contains the signature, a valid file fails with "Its file list is corrupt". The check should confirm that the record's comment length reaches the end of the file.
- [ ] **Pages can go missing without a warning (`parseCentralDirectory`).** Parsing stops at the entry count the archive declares. If that count is lower than the real number of entries, the remaining pages are dropped and the book simply looks shorter. A mismatch should be reported, or the parser should read the whole directory.
- [ ] **Zooming during a load can lose your place (`updateZoom`).** Page positions aren't known until the first zoom change or the end of the load. If you scroll during a load and then move the zoom slider, the view jumps back to the top. Zoom should either wait for known positions or positions should be calculated as pages load.
- [ ] **Older archives can sort incorrectly (`parseCentralDirectory`).** Filenames are always decoded as UTF-8, and the archive's encoding flag is ignored. Names stored in CP437 can turn into replacement characters and display in the wrong page order. `TextDecoder` doesn't support CP437, so a fix needs its own character table.
- [ ] **Malformed ZIP64 fields aren't detected (`readZip64Values`).** If the ZIP64 extra field is missing, `0xffffffff` is kept as a real size or offset, so a stored page can read through to the end of the file. The field's declared size also isn't checked, so a field that's too short reads into the bytes after it.
- [ ] **Some typed zoom values are misread.** The number field uses `parseInt`, which rejects `1e2` even though it's valid and equal to 100, and turns `100.9` into 100.

### Testing

- [ ] **Test on phones.** The viewport tag makes the page lay out at the device width, and this hasn't been tested on a phone or in mobile emulation.
- [ ] **Check decimal input.** With `lang="en"` on the page, Chrome may read a typed decimal like `100,5` differently from before. Whole numbers aren't affected.

### Cleanup

These are harmless and low priority:
- [ ] `min-height: 0` on `#imageContainer` looks redundant, because `overflow: auto` already allows it to shrink.
- [ ] The `Math.min` around `scrollTop` in `updateZoom` looks redundant, because browsers limit that value themselves.
