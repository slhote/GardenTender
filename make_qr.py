# /// script
# dependencies = ["qrcode[pil]"]
# ///

"""Generate GardenTender test QR codes as PNG files.

Setup:   pip install "qrcode[pil]"
Usage:   python make_qr.py                       # built-in test payloads -> ./qr_codes
         python make_qr.py PAYLOAD [PAYLOAD ...]  # your own payloads
         python make_qr.py -o out_dir ...         # choose the output folder

Payload format understood by the app:
  gardentender://plant/<id>                view a plant
  gardentender://plant/<id>?action=water   log a watering
Anything else shows "Not a GardenTender code".
"""
import argparse
import re
from pathlib import Path

import qrcode

DEFAULT_PAYLOADS = [
    "gardentender://plant/tomato-1",
    "gardentender://plant/tomato-1?action=water",
    "gardentender://plant/basil-2?action=water",
    "gardentender://plant/my%20mint",
    "hello world",
]


def filename_for(payload: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", payload.removeprefix("gardentender://")).strip("_")
    return f"{slug or 'qr'}.png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("payloads", nargs="*", help="text to encode (default: built-in test set)")
    parser.add_argument("-o", "--out", default="qr_codes", help="output folder (default: qr_codes)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for payload in args.payloads or DEFAULT_PAYLOADS:
        path = out_dir / filename_for(payload)
        qrcode.make(payload, box_size=12, border=4).save(path)
        print(f"{path}  <-  {payload}")


if __name__ == "__main__":
    main()
