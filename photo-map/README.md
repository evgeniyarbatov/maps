# Photo Map

## Setup

```bash
make install
```

## Extract photo data

```bash
make extract-photos INPUT_DIR=/Users/zhenya/Downloads/soc-son
```

Outputs:
- `site/public/photos.json`
- Thumbnails in `site/public/thumbs`
- Original images in `site/public/photos`

## Run the site

```bash
cd site
npm install
npm run dev
```

## Use the map

- Click a thumbnail on the map to select/deselect it.
- Use the input fields to jump to `lat`, `lon`, and `z`.
- Use the download button to download the original images for the current selection.
