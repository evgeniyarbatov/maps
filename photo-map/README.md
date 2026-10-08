# Photo Map

Local web app to browse geotagged photos on a map and find them by `lat`, `lon`.

## Extract metadata

```bash
make extract-photos INPUT_DIR=$HOME/Downloads/soc-son
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
