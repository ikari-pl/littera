# App Icons

Tauri requires these icon files for bundling:

- `32x32.png` (32x32 pixels)
- `128x128.png` (128x128 pixels)
- `128x128@2x.png` (256x256 pixels)
- `icon.icns` (macOS app icon bundle)
- `icon.ico` (Windows icon)

The current icons are placeholders generated from a 32x32 source.
Replace them with final artwork by running:

```bash
cargo tauri icon path/to/source-icon.png
```

This command auto-generates all required sizes and formats from a
source image (minimum 1024x1024 recommended).
