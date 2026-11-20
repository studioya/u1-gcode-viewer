# U1 G-code Viewer

A 3D G-code viewer and pre-print checker for the **Snapmaker U1** tool changer. It's a single HTML page. Open a `.gcode` file and it's read entirely in your browser: nothing is uploaded.

## Using it

Open `index.html` in a recent desktop browser (Chrome, Edge, Firefox or Safari with WebGL 2). To send prints to the printer, open it from `localhost` instead (see [Sending a print to the printer](#sending-a-print-to-the-printer)). Drop a `.gcode` file on the page or use **Open G-code**. An example two-colour print loads on start.

The page loads three.js from jsDelivr and its fonts from Google Fonts, so it needs an internet connection the first time.

## What it shows

- **Toolpaths in 3D**, coloured by tool (using the filament colours stored in the file), feature, speed or volumetric flow. Click legend entries to hide tools or features.
- **A layer range and move scrubber**, with play-through and buttons that jump to the previous or next tool swap.
- **Tool-swap markers** where each incoming head starts printing, and the **four docks** drawn at their positions from the U1 firmware config, in the nozzle plane of the current layer.
- **The G-code behind any move**, with the matching line highlighted.
- **A summary**: the slicer's print time next to the viewer's own estimate, a breakdown of time spent extruding, travelling and swapping, time per layer, filament per tool, and labeled objects.

## Sending a print to the printer

**Send to printer** uploads the open file to the U1 through Moonraker, the API behind Fluidd. It sends the same upload request Fluidd does, and can start the print straight away. It works with stock U1 firmware and needs no changes to the printer.

### Opening the viewer

The browser sends the file straight to the printer, and the U1 only accepts that from a page served on your own computer at `localhost`. Double-clicking `index.html` opens it from disk, which the printer refuses. Use one of these instead. Both need [Python](https://www.python.org/downloads/).

**On Windows: the U1 Viewer shortcut (easiest).** Double-click **Install shortcuts.cmd** once. It adds a **U1 Viewer** shortcut to your Desktop and Start menu. To pin it to the taskbar, open Start, right-click **U1 Viewer**, then **Pin to taskbar**.

Clicking the shortcut opens the viewer in its own Chrome or Edge window, without tabs or an address bar. Behind it, `launcher/u1_viewer.pyw` serves the page at `http://localhost:8765`:

- It's visible to this computer only, and serves only the viewer page, not the rest of the folder.
- Clicking the shortcut again opens another window instead of starting a second server.
- The server stops by itself after two hours without page loads. Windows that are already open keep working.
- To remove the shortcuts, run `python launcher\u1_viewer.pyw --uninstall`.
- If you move this folder, run **Install shortcuts.cmd** again.

**Running in the background.** Install shortcuts.cmd also starts the viewer in the background whenever you sign in to Windows, at `http://localhost:8765`, with no window. The shortcut then just opens a window onto it. `python launcher\u1_viewer.pyw --uninstall` removes the sign-in entry along with the shortcuts.

**Opening a file by name.** G-code files saved in `Documents\U1 jobs` open with `http://localhost:8765/?file=<file name>`. Only that folder is served, only files ending in `.gcode`, `.gco` or `.g`, and only to this computer. This is how Claude opens a file in the viewer for you: it saves the file there and opens the address in the Claude desktop app's browser pane.

**Anywhere: run a server yourself.**

1. In the viewer's folder, run:

   ```bash
   python -m http.server 8000 --bind 127.0.0.1
   ```

2. Open **http://localhost:8000**.
3. Press **Ctrl+C** in that window to stop the server when you're done.

`--bind 127.0.0.1` keeps the server visible to your computer only. Don't use `--bind 0.0.0.0`: it shares the folder with every device on your network.

**In the Claude desktop app:** the repo includes `.claude/launch.json`. In a Claude Code session in this folder, ask Claude to "open the U1 viewer", and it opens the viewer in Claude's browser pane, at `http://localhost:8765`.

Each browser remembers the printer address separately, so enter it once in each.

### Sending a file

1. Open your G-code file, then click **Send to printer**.
2. Enter the address you open Fluidd at, for example `192.168.1.50`. **Test connection** shows whether the printer is reachable and whether it's idle.
3. Leave **Start printing as soon as it's uploaded** ticked to print right away, or untick it to only add the file to the printer's file list.

Some safeguards:

- If the Checks tab lists any problems, you have to tick a box to start the print anyway. Uploading without printing doesn't need it.
- If the printer is already printing or paused, or Klipper isn't ready, the file is only uploaded.
- The printer address (and API key, if you set one) is remembered in this browser only, unless you untick **Remember**.

A print started from the viewer is a real print. Start one only when someone can keep an eye on the printer.

### If it can't reach the printer

- **Check the page address** starts with `http://localhost` or `http://127.0.0.1`, not `file://`.
- **Check Fluidd opens** at the printer address from the same computer.
- **Allow local network access** if Chrome or Edge asks, for the viewer only.
- **Don't use an HTTPS copy.** A page served over HTTPS, such as GitHub Pages, can't call a printer over plain HTTP.
- **API key.** If the printer asks for one, paste it under **API key**. Moonraker shows the key at `http://<printer>/access/api_key`.

Why `localhost` works: the U1's stock `moonraker.conf` lists `*://localhost:*`, `*.local` and `*.lan` in `cors_domains`, so pages from those addresses may call the printer. This was checked on a U1 running stock firmware. If your printer's settings differ, add the page's address to `cors_domains` under `[authorization]`, for example through the community [Extended Firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)'s `extended/moonraker/` folder.

### Security notes

- The viewer can do only what Fluidd can already do from your browser.
- three.js is pinned with integrity hashes, so the browser refuses a modified copy from the CDN.
- The U1's stock settings let any device on your network control the printer without a login (`trusted_clients`), and allow any page served from `localhost` to call it. Keep the printer on a network only trusted devices use, never forward its ports to the internet, and decline local-network access requests from websites you don't trust.

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
