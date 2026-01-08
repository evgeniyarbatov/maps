# Photo Map

Photo Map is a local web app that plots geotagged photos on a map and lets you browse thumbnails while keeping originals via symlinks.

<img width="1538" height="841" alt="Photo Map" src="https://github.com/user-attachments/assets/5330af52-bced-4e0a-b1cf-8d1ac773badb" />

## Extract metadata

```bash
make extract-photos INPUT_DIR=/Users/zhenya/Downloads/soc-son
```

Outputs:
- `site/public/photos.json`
- Thumbnails in `site/public/thumbs`
- Original images are symlinked in `site/public/photos`

## Run

```bash
make run
```

## Use

- Click a thumbnail on the map to select/deselect it.
- Use the input fields to jump to `lat`, `lon`
- Use the download button to download the original images for the current selection.
