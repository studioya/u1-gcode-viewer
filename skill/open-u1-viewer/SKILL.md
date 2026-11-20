---
name: "open-u1-viewer"
description: "Open Yarden's U1 G-code Viewer in the Claude desktop app's browser pane, optionally with a G-code file loaded, so it can be checked and sent to the Snapmaker U1 from there. Use when Yarden says to send or open a file in the U1 viewer, open the viewer, preview G-code, or check a print before sending it to the U1."
---

# Open the U1 viewer

"The viewer" is Yarden's own U1 G-code Viewer (GitHub `studioya/u1-gcode-viewer`), the version with **Send to printer**. It runs on Yarden's Windows laptop at `http://localhost:8765`, served by `launcher/u1_viewer.pyw --serve`, which starts at Windows sign-in.

That address is on the laptop, the same machine as the desktop app's browser pane, so the pane can open it even when this session runs in the cloud. The rule that the pane can't open localhost servers applies only to servers Claude starts itself, not to this one.

Never substitute an artifact copy, an older artifact version, or a page in Chrome. Send to printer only works from the localhost page.

## Steps

1. **Load the built-in browser tools** (`Claude_Browser__*`, with whichever prefix this session has, such as `mcp__remote-devices__Claude_Browser__`) in one ToolSearch call. Read the built-in-browser skill if it's listed.

2. **If there's a G-code file to show, put it in the U1 jobs folder on the laptop.** The folder is `C:\Users\yarde\OneDrive\Documents\U1 jobs`, which is Windows' Documents folder. The viewer also looks in `C:\Users\yarde\Documents\U1 jobs`, so either folder works.
   - Use the device file tools, if this session has them: `get_device_info`, then `device_list_dir` on the folder. If the folder isn't connected, request it once with `device_request_folder_access`, with the reason "to drop G-code files where the U1 viewer can open them".
   - Copy the file with `device_commit_files`. Its source can be a `fileUuid` from SendUserFile or a `stagedPath` under /mnt/user-data/outputs/.
   - Keep the file name plain: letters, digits, spaces and `-_.()`, ending in `.gcode`, `.gco` or `.g`. Don't use slashes, colons or `..`.
   - **No device file tools?** Send the file with SendUserFile and ask Yarden to save it into the U1 jobs folder, then continue.

3. **Open the viewer in the browser pane** with `preview_start` (or `navigate` if a pane tab is already open):
   - with a file: `http://localhost:8765/?file=<URL-encoded file name>`, for example `?file=benchy%20PLA.gcode`
   - without a file: `http://localhost:8765/`

4. **Confirm it loaded** with `get_page_text`, not a screenshot. The file name shows under "G-code Viewer" in the Summary tab. Report in a line or two:
   - print time, layers and filament
   - any check in the Checks tab that isn't "FINE"

## If it doesn't load

- **The page doesn't load at all (connection refused).** The background server isn't running. Ask Yarden to click the **U1 Viewer** shortcut once, which starts it. If they never set it up, they double-click **Install shortcuts.cmd** in the repo folder. Then retry step 3. Don't try to start the server yourself from a cloud session.
- **"Couldn't open <file>: it isn't in the U1 jobs folder".** The file isn't there, or the name in the address doesn't match it exactly. Check with `device_list_dir` and retry.
- **The browser pane is offline.** The Claude desktop app isn't open on the laptop. Say so; don't fall back to Chrome or an artifact.

## Sending to the printer

The viewer sends prints itself, through the U1's Moonraker at `10.0.0.18`.

1. Click **Send to printer** in the viewer.
2. If the address field is empty, enter `10.0.0.18` and leave **Remember the address in this browser** ticked.
3. **Start printing as soon as it's uploaded** switches the button between **Upload and print** and **Upload**. If the printer is busy, the viewer only uploads.

Never click **Send to printer** or start a print unless Yarden asks for it in this conversation. A start is a real print on the U1: first confirm the file name and that someone is at the printer. After sending, read the dialog's status line with `get_page_text` and report it.
