# Photo Map

Photo Map is a local web app that plots geotagged photos on a map and lets you browse thumbnails while keeping originals via symlinks.

## Extract photo data (run once)

```bash
make extract-photos INPUT_DIR=/Users/zhenya/Downloads/soc-son
```

Outputs:
- `site/public/photos.json`
- Thumbnails in `site/public/thumbs`
- Original images are symlinked in `site/public/photos`

## Run the site

```bash
make run
```

## Use the map

- Click a thumbnail on the map to select/deselect it.
- Use the input fields to jump to `lat`, `lon`
- Use the download button to download the original images for the current selection.
