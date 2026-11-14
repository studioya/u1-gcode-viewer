# U1 G-code Viewer

A 3D G-code viewer and pre-print checker for the **Snapmaker U1** tool changer. It's a single HTML page. Open a `.gcode` file and it's read entirely in your browser: nothing is uploaded.

## Using it

Open `index.html` in a recent desktop browser (Chrome, Edge, Firefox or Safari with WebGL 2). Drop a `.gcode` file on the page or use **Open G-code**. An example two-colour print loads on start.

The page loads three.js from jsDelivr and its fonts from Google Fonts, so it needs an internet connection the first time.

## What it shows

- **Toolpaths in 3D**, coloured by tool (using the filament colours stored in the file), feature, speed or volumetric flow. Click legend entries to hide tools or features.
- **A layer range and move scrubber**, with play-through and buttons that jump to the previous or next tool swap.
- **Tool-swap markers** where each incoming head starts printing, and the **four docks** drawn at their positions from the U1 firmware config, in the nozzle plane of the current layer.
- **The G-code behind any move**, with the matching line highlighted.
- **A summary**: the slicer's print time next to the viewer's own estimate, a breakdown of time spent extruding, travelling and swapping, time per layer, filament per tool, and labeled objects.

## Sending a print to the printer

**Send to printer** uploads the open file to the U1 through Moonraker, the API behind Fluidd. It sends the same upload request Fluidd does, and can start the print straight away.

1. Open your G-code file, then click **Send to printer**.
2. Enter the address you open Fluidd at, for example `192.168.1.50`. **Test connection** shows whether the printer is reachable and whether it's idle.
3. Leave **Start printing as soon as it's uploaded** ticked to print right away, or untick it to only add the file to the printer's file list.

Some safeguards:

- If the Checks tab lists any problems, you have to tick a box to start the print anyway. Uploading without printing doesn't need it.
- If the printer is already printing or paused, or Klipper isn't ready, the file is only uploaded.
- The address (and API key, if you set one) is remembered in this browser only, unless you untick **Remember**.

### If it can't reach the printer

The browser talks to the printer directly, so Moonraker has to accept requests from this page. If Fluidd opens but the viewer says it can't reach the printer, add the page's origin to `cors_domains` in `moonraker.conf` and restart Moonraker. The dialog tells you which origin to add.

The safest setup is to serve the viewer from your own computer and allow just that address:

```bash
python -m http.server 8000
```

Run that in the viewer's folder, open `http://localhost:8000`, and add this to `moonraker.conf`:

```ini
[authorization]
cors_domains:
    http://localhost:8000
```

If you open `index.html` straight from disk, the browser reports the page's origin as `null`. Adding `null` to `cors_domains` works, but it also lets any other HTML file opened from disk control the printer, so prefer the local server.

Two browser rules also apply:

- A page served over **HTTPS** (such as GitHub Pages) can't call a printer over plain HTTP. Use the viewer from your computer instead.
- Recent versions of Chrome and Edge may ask for permission to access devices on your local network the first time. Allow it.

Moonraker lets addresses listed in `trusted_clients` in without an API key. If yours does ask for one, paste it under **API key**. Moonraker shows the key at `http://<printer>/access/api_key` to a client it already trusts.

This was tested against a simulated Moonraker server, not a real U1. Snapmaker's stock `moonraker.conf` may not allow other origins until you add one.

## What it checks

Every check links to the source it comes from.

| Check | Basis |
|---|---|
| Extrusion outside the 270 × 270 mm plate, or taller than the build height | Snapmaker specs |
| Travel moves passing through plastic that's already printed (toolhead collisions) | Owner reports, including the prime tower's "No sparse layers" setting |
| File sliced for a different printer | Owner reports of tool changes knocking prints over |
| Number of tool swaps and time spent docking | Slicer's tool change time; Snapmaker quotes about 5 s |
| Swaps that pick up a head that wasn't preheated | U1 change G-code waits with M109 |
| Missing prime tower, high prime volume, tall tower on a narrow brim | Owner reports |
| PLA and PETG sharing a prime tower | Owner reports |
| TPU with a long tool-change retraction | 3D Print Wiki |
| Low bed temperature for PETG | Owner reports about the stock PETG profiles |
| Flow above the hotend's 32 mm³/s, speed above 500 mm/s, acceleration above 20,000 mm/s² | Snapmaker specs |
| Very low max volumetric speed in a filament profile | Owner reports |
| Very large files (scan timeouts after network upload) | Owner reports |
| Commands not in Snapmaker's published U1 firmware | [Snapmaker/u1-klipper](https://github.com/Snapmaker/u1-klipper) |
| Objects not labeled (can't cancel one object mid-print) | Klipper exclude-object |

A passing check doesn't guarantee a good print.

## How it works

- A Web Worker streams the file in 8 MB chunks and parses it byte by byte. A 74 MB file reads in a few seconds.
- It understands the comment tags Snapmaker Orca and OrcaSlicer write (`;LAYER_CHANGE`, `;TYPE:`, `;WIDTH:`, wipe-tower blocks, thumbnails, the config block), as well as Bambu-style tags. Files without layer tags fall back to detecting layers from Z.
- Extrusions are drawn as shaded instanced ribbons on the GPU. Nearly collinear segments are merged for drawing, so the move scrubber can step over several lines at once.
- The time estimate models Klipper-style junction speeds with the U1's limits (500 mm/s, accelerations from the file, 8 mm/s square-corner velocity from the firmware config) plus the slicer's tool-change time. It skips heat-up waits and the start routine.
- The collision check keeps a 1 mm height map of printed plastic and tests every travel move against it. The path to and from a dock is approximated, because the firmware controls that move.

## Limits

- Tested with generated files, U1 headers from Snapmaker Orca and OrcaSlicer, and files from public repositories. A complete real Snapmaker Orca U1 print file wasn't available for testing.
- Very large files can be slow to display on phones and low-power GPUs.

## Credits

- [three.js](https://threejs.org) (MIT) for rendering.
- U1 limits from [Snapmaker's specs](https://www.snapmaker.com/en-US/snapmaker-u1/specs) and the [U1 FAQ](https://forum.snapmaker.com/t/u1-faq-official-info-summary/39648). Dock positions and the firmware command list come from [Snapmaker/u1-klipper](https://github.com/Snapmaker/u1-klipper). G-code tags come from [Snapmaker/OrcaSlicer](https://github.com/Snapmaker/OrcaSlicer).
- The checks draw on problems U1 owners have reported on [r/snapmaker](https://www.reddit.com/r/snapmaker/) and the [3D Print Wiki](https://3dprint.wiki/printers/snapmaker/u1).

Not affiliated with or endorsed by Snapmaker.

## License

[MIT](LICENSE)
