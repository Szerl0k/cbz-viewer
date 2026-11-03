# Testing

The viewer is tested by opening generated archives in a browser and comparing the results with the tables below.

## Generate the archives

The script needs Python 3 and has no other dependencies:

```sh
python3 tests/make_fixtures.py
```

The archives are written to `tests/fixtures/`, which Git ignores. `zip64-large-offset.cbz` reports a size of about 4.1 GiB, but it's a sparse file, so on most file systems it uses only a few kilobytes of disk. Copying it to another location can write the full size.

## Test each archive

Open `index.html` and pick each archive in turn. Reload the page between archives, and keep the browser console open: no test should log an uncaught error.

### Archives that load fully

The loading message fades, no warning appears, and the counter reads `Page 1 / N`.

| Archive | Pages | What it checks |
|---|---|---|
| `basic` | 3 | Stored and deflated pages |
| `webp` | 4 | WebP pages |
| `data-descriptors` | 3 | Sizes that are only in the central directory |
| `macos-metadata` | 3 | `__MACOSX/` and `._*` entries are left out |
| `unpadded-names` | 3 | Natural page order: red, then green, then blue |
| `short-book` | 2 | A book that fits on screen starts on page 1 |
| `large-book` | 400 | A book that takes a few seconds to load |
| `exactly-65535-entries` | 3 | The highest entry count without ZIP64 |
| `zip64-many-entries` | 3 | ZIP64 end records |
| `zip64-large-offset` | 3 | ZIP64 entry offsets past 4 GiB |

### Archives that load with a warning

Two pages are displayed, and the toolbar reads `1 of 3 pages could not be loaded`.

| Archive | What it checks |
|---|---|
| `corrupt-page` | A page that can't be decompressed |
| `undecodable-page` | A page that isn't a valid image |
| `partly-encrypted` | One encrypted page |
| `unsupported-compression` | A page with an unsupported compression method |

### Archives that fail with an error

The message stays on screen, no pages are displayed, the counter reads `Page 0 / 0`, and the file input is cleared.

| Archive | Expected message |
|---|---|
| `not-a-zip` | Could not load this file. It may be 7z or RAR encoded, or truncated. Only ZIP-encoded CBZ files are supported. |
| `truncated` | Could not load this file. It may be 7z or RAR encoded, or truncated. Only ZIP-encoded CBZ files are supported. |
| `no-images` | No images were found in this archive. |
| `all-encrypted` | This archive is encrypted. Encrypted archives are not supported. |
| `all-pages-corrupt` | None of the 3 pages could be loaded. |
| `bad-central-directory` | Could not read this archive. Its file list is corrupt. |
| `truncated-central-directory` | Could not read this file. It may be corrupt or truncated. |
| `zip64-missing-records` | Could not read this archive. Its ZIP64 records are missing or invalid. |
| `zip64-invalid-record` | Could not read this archive. Its ZIP64 records are missing or invalid. |

## Test zoom and window resizing

Open `large-book` at 100% and check that a whole page is visible above the toolbar without scrolling.

Open `basic`, whose pages have a natural size of 400×600. These sizes assume the window is at least 700 pixels tall and 400 wide.

1. **Scale pages:** set the zoom to 50, then 200. The pages become 200×300 and then 800×1200, which is larger than their natural size.
2. **Pan a zoomed page:** with the zoom at 250, make the window narrower than the pages. You can scroll sideways to both edges of the page.
3. **Keep your place:** scroll halfway down page 2, then change the zoom. The same part of page 2 stays in view.
4. **Resize the window:** at 100%, make the window narrower than the pages. The pages shrink to fit, and the counter stays on the same page.
5. **Type a zoom value:** select the number field and type `150`. The field doesn't change while you type, and the zoom applies when you press Enter.
6. **Type an invalid value:** type `999` and press Enter, or clear the field and click elsewhere. The field returns to the last valid zoom.

## Test opening several books

Run these without reloading the page, unless a step says otherwise.

1. **Replace a book:** open `basic`, then `corrupt-page`. The counter reads `Page 1 / 2` and the warning appears. Open `basic` again, and the counter reads `Page 1 / 3` with no warning.
2. **Keep zoom:** set the zoom to 50 and open another book. The new pages use the same zoom.
3. **Retry after an error:** open `not-a-zip` twice in a row. The error appears both times.
4. **Recover from an error:** open `not-a-zip`, then `basic`. The message fades and three pages are displayed.
5. **Replace a running load:** open `large-book`, and open `basic` while it's still loading. Only the three pages of `basic` are displayed, and the counter stays at `Page 1 / 3`.
