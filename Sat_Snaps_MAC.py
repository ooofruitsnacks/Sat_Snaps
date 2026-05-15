#!/usr/bin/env python3
"""
Generates a satellite image with Apple Maps (MapKit) using DD X,Y coordinates
Made by Owen Edwards / ACS "a creative solution"
an open source program made for everyone to enjoy, because fuck google and their map API keys.
v.1.0.1

"""
import os
import re
import sys
import stat
import time
import secrets
import tempfile
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

OUTPUT_DIR = Path.home() / "Pictures"

MAX_DIMENSION = 8192          # max width or height in pixels
MIN_DIMENSION = 64
MAX_SPAN_DEGREES = 1.0
MIN_SPAN_DEGREES = 0.0001

COORD_RE = re.compile(r"^-?\d{1,3}(?:\.\d+)?,-?\d{1,3}(?:\.\d+)?$")

HTTP_USER_AGENT = "sat-track-snaps/1.0 (+local script)"

LOCATION_OPTIONS = [
    {"title": "Current Location",           "coords": (0, 0)},
    {"title": "Denver, USA",            "coords": (39.739200, -104.990300)},
    {"title": "NYC,USA",            "coords": (40.712800, -74.006000)},
    {"title": "Buenos Aires, Argentina",           "coords": (-34.603700, -58.381600)},
    {"title": "Cape Town, Africa",          "coords": (-33.924900, 18.424100)},
    {"title": "Madrid, Spain",          "coords": (40.416800, -3.703800)},
    {"title": "Berlin, Germany",            "coords": (52.520000, 13.405000)},
    {"title": "Dubai, UAE",         "coords": (25.204800, 55.270800)},
    {"title": "Moscow, Russia",         "coords": (55.755800, 37.617300)},
    {"title": "Beijing, China",         "coords": (39.904200, 116.407400)},
    {"title": "Jakarta, Indonesia",         "coords": (-6.208800, 106.845600)},
    {"title": "Melbourne, Australia",           "coords": (-37.813600, 144.963100)},
]
def validate_coordinates(lat, lng):
    """Reject coordinates outside Earth's valid range."""
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return None
    return lat, lng


def clamp_dimensions(width, height, span_degrees):
    """Clamp image size and span to safe bounds."""
    width = max(MIN_DIMENSION, min(int(width), MAX_DIMENSION))
    height = max(MIN_DIMENSION, min(int(height), MAX_DIMENSION))
    span_degrees = max(MIN_SPAN_DEGREES, min(float(span_degrees), MAX_SPAN_DEGREES))
    return width, height, span_degrees


def sanitize_title(s):
    """Strip control chars / RTL overrides from displayed strings (Item #5)."""
    if not isinstance(s, str):
        return ""
    return "".join(c for c in s if c.isprintable() and ord(c) >= 0x20
                   and c not in ("\u202a", "\u202b", "\u202c", "\u202d", "\u202e"))

def safe_resolve_output_dir():
    """
    Verify OUTPUT_DIR is a real directory (not a symlink) and create it if
    missing. Refuses to follow symlinks. Returns the resolved Path or None.
    """
    try:
        if OUTPUT_DIR.exists():
            # Use lstat() to detect symlink rather than target
            st = os.lstat(OUTPUT_DIR)
            if stat.S_ISLNK(st.st_mode):
                messagebox.showerror(
                    "Unsafe output directory",
                    f"{OUTPUT_DIR} is a symbolic link. Refusing to write.",
                )
                return None
            if not OUTPUT_DIR.is_dir():
                messagebox.showerror(
                    "Unsafe output directory",
                    f"{OUTPUT_DIR} exists but is not a directory.",
                )
                return None
        else:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
        return OUTPUT_DIR
    except OSError as e:
        messagebox.showerror("Filesystem error", f"Cannot prepare {OUTPUT_DIR}: {e}")
        return None


def safe_write_bytes(directory: Path, suffix: str, data: bytes,
                     final_name: str | None = None) -> Path | None:
    """
    Atomically write `data` to a temp file inside `directory` using
    O_CREAT | O_EXCL | O_NOFOLLOW | O_WRONLY with mode 0600. O_NOFOLLOW
    causes the open() to fail if the path is a symlink, defeating
    symlink-based TOCTOU attacks on the temp file itself.

    If `final_name` is provided, the temp file is renamed into place
    after verifying the destination is not a symlink. Returns the final
    Path, or None on error.
    """
    # Build a unique temp path manually so we control the open flags.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
    # O_CLOEXEC is a good extra default on POSIX:
    flags |= getattr(os, "O_CLOEXEC", 0)

    tmp_path = None
    fd = -1
    for _ in range(8):  # retry on the astronomically unlikely collision
        candidate = directory / f".tmp-{secrets.token_hex(16)}{suffix}"
        try:
            fd = os.open(str(candidate), flags, 0o600)
            tmp_path = str(candidate)
            break
        except FileExistsError:
            continue
        except OSError as e:
            messagebox.showerror("Write error", f"Cannot create temp file: {e}")
            return None

    if fd < 0 or tmp_path is None:
        messagebox.showerror("Write error", "Could not allocate temp file.")
        return None

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        messagebox.showerror("Write error", str(e))
        return None

    if final_name is None:
        return Path(tmp_path)

    if "/" in final_name or "\\" in final_name or final_name.startswith("."):
        os.unlink(tmp_path)
        messagebox.showerror("Invalid filename", final_name)
        return None

    final_path = directory / final_name

    if final_path.exists() or final_path.is_symlink():
        try:
            if stat.S_ISLNK(os.lstat(final_path).st_mode):
                os.unlink(tmp_path)
                messagebox.showerror(
                    "Refusing to overwrite symlink", str(final_path)
                )
                return None
        except OSError:
            pass
    os.replace(tmp_path, final_path)
    os.chmod(final_path, 0o600)
    return final_path

def get_location_coreLocation(timeout=5.0):
    """Get current location via CoreLocation, with proper auth handling."""
    try:
        from CoreLocation import (
            CLLocationManager,
            kCLAuthorizationStatusAuthorized,
            kCLAuthorizationStatusAuthorizedAlways,
            kCLAuthorizationStatusDenied,
            kCLAuthorizationStatusRestricted,
        )
        from Foundation import NSRunLoop, NSDate
    except ImportError:
        return None

    mgr = CLLocationManager.alloc().init()
    try:
        status = CLLocationManager.authorizationStatus()
        if status in (kCLAuthorizationStatusDenied,
                      kCLAuthorizationStatusRestricted):
            print("CoreLocation denied/restricted by user.", file=sys.stderr)
            return None
    except Exception:
        pass

    mgr.startUpdatingLocation()
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            loc = mgr.location()
            if loc is not None:
                coord = loc.coordinate()
                return validate_coordinates(coord.latitude, coord.longitude)
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(0.2)
            )
    finally:
        mgr.stopUpdatingLocation()
    return None


def get_location_ip():
    """
    Fallback: approximate location via IP geolocation.
    Requires explicit user confirmation (Item #7) and validates response (Item #3).
    """
    consent = messagebox.askyesno(
        "Network geolocation?",
        "CoreLocation is unavailable. Use ipinfo.io/json with HTTPS? ",
    )
    if not consent:
        return None

    try:
        import requests
        r = requests.get(
            "https://ipinfo.io/json",
            timeout=5,
            headers={"User-Agent": HTTP_USER_AGENT},
            verify=True,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"IP geolocation failed: {e}", file=sys.stderr)
        return None

    loc_raw = data.get("loc", "")
    if not isinstance(loc_raw, str) or not COORD_RE.match(loc_raw):
        print(f"Rejecting malformed loc value: {loc_raw!r}", file=sys.stderr)
        return None

    try:
        lat_s, lng_s = loc_raw.split(",")
        return validate_coordinates(lat_s, lng_s)
    except ValueError:
        return None


def get_location():
    loc = get_location_coreLocation()
    if loc:
        return loc
    print("Falling back to IP lookup (user consent required)…")
    return get_location_ip()

def fetch_satellite_image_apple(lat, lng, width=1920, height=1080,
                                 span_degrees=0.0006, timeout=20.0):
    """
    Render a satellite snapshot using Apple's MapKit MKMapSnapshotter.
    Returns JPEG bytes, or None on failure.
    """
    coords = validate_coordinates(lat, lng)
    if coords is None:
        print("Invalid coordinates passed to snapshotter.", file=sys.stderr)
        return None
    lat, lng = coords
    width, height, span_degrees = clamp_dimensions(width, height, span_degrees)

    try:
        from MapKit import (
            MKMapSnapshotter,
            MKMapSnapshotOptions,
            MKMapTypeSatellite,
            MKCoordinateRegionMake,
            MKCoordinateSpanMake,
        )
        from CoreLocation import CLLocationCoordinate2DMake
        from Foundation import NSRunLoop, NSDate
        from Quartz import NSBitmapImageRep, NSBitmapImageFileTypeJPEG
        from AppKit import NSMakeSize
    except ImportError as e:
        messagebox.showerror(
            "Missing dependency",
            f"Required PyObjC framework not available: {e}\n\n"
            "Install with:\n  pip3 install pyobjc-framework-MapKit "
            "pyobjc-framework-Quartz",
        )
        return None

    center = CLLocationCoordinate2DMake(lat, lng)
    span = MKCoordinateSpanMake(span_degrees, span_degrees)
    region = MKCoordinateRegionMake(center, span)

    options = MKMapSnapshotOptions.alloc().init()
    options.setRegion_(region)
    options.setSize_(NSMakeSize(width, height))
    options.setMapType_(MKMapTypeSatellite)
    options.setShowsBuildings_(True)
    try:
        options.setScale_(2.0)
    except AttributeError:
        pass

    snapshotter = MKMapSnapshotter.alloc().initWithOptions_(options)

    result = {"image": None, "error": None}
    done = threading.Event()
    lock = threading.Lock()

    def completion(snapshot, error):
        with lock:
            if error is not None:
                result["error"] = str(error)
            elif snapshot is not None:
                result["image"] = snapshot.image()
        done.set()

    snapshotter.startWithCompletionHandler_(completion)

    deadline = time.time() + timeout
    while not done.is_set() and time.time() < deadline:
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.05)
        )

    if not done.wait(timeout=0):  # final check
        print("MKMapSnapshotter timed out.", file=sys.stderr)
        return None

    with lock:
        err = result["error"]
        ns_image = result["image"]

    if err:
        print(f"MKMapSnapshotter error: {err}", file=sys.stderr)
        return None
    if ns_image is None:
        return None

    tiff_data = ns_image.TIFFRepresentation()
    if tiff_data is None:
        return None
    bitmap = NSBitmapImageRep.imageRepWithData_(tiff_data)
    jpeg_props = {"NSImageCompressionFactor": 0.92}
    jpeg_data = bitmap.representationUsingType_properties_(
        NSBitmapImageFileTypeJPEG, jpeg_props
    )
    if jpeg_data is None:
        return None
    return bytes(jpeg_data)

def list_dialog(title, options):
    """Show a selection dialog with sanitized titles."""
    root = tk.Tk()
    root.title(sanitize_title(title) or "Select")
    root.geometry("320x380")
    selection = {"value": None}

    tk.Label(root, text=sanitize_title(title),
             font=("Helvetica", 14, "bold")).pack(pady=8)

    listbox = tk.Listbox(root, width=40, height=15)
    for opt in options:
        listbox.insert(tk.END, sanitize_title(opt.get("title", "")))
    listbox.pack(padx=10, pady=5, fill="both", expand=True)

    def on_ok():
        idx = listbox.curselection()
        if idx:
            selection["value"] = options[idx[0]]
        root.destroy()

    def on_cancel():
        root.destroy()

    btns = tk.Frame(root)
    btns.pack(pady=8)
    tk.Button(btns, text="OK", width=10, command=on_ok).pack(side="left", padx=5)
    tk.Button(btns, text="Cancel", width=10,
              command=on_cancel).pack(side="left", padx=5)
    listbox.bind("<Double-Button-1>", lambda _e: on_ok())
    root.mainloop()
    return selection["value"]


def open_image(path: Path):
    """
    Open the image with the default macOS viewer. Uses `--` to defeat
    argument-injection (Item #4) and resolves the path absolutely.
    """
    abs_path = path.resolve(strict=True)
    try:
        abs_path.relative_to(OUTPUT_DIR.resolve(strict=True))
    except ValueError:
        print("Refusing to open file outside output directory.", file=sys.stderr)
        return
    subprocess.run(["/usr/bin/open", "--", str(abs_path)], check=False)

def main():
    out_dir = safe_resolve_output_dir()
    if out_dir is None:
        return

    opt = list_dialog("Select Location", LOCATION_OPTIONS)
    if opt is None:
        return

    if opt["coords"] == (0, 0):
        loc = get_location()
    else:
        loc = validate_coordinates(*opt["coords"])

    if not loc:
        messagebox.showerror(
            "Location error",
            "Cannot determine location. Check Privacy & Security → Location "
            "Services for your terminal/Python, or your internet connection.",
        )
        return

    lat, lng = loc
    jpeg_data = fetch_satellite_image_apple(
        lat, lng, width=1920, height=1080, span_degrees=0.0006,
    )
    if not jpeg_data:
        print("Failed to render map", file=sys.stderr)
        return

    temp_path = safe_write_bytes(out_dir, ".jpg", jpeg_data)
    if temp_path is None:
        return

    open_image(temp_path)

    if messagebox.askyesno(
            "Save Image",
            "Save the satellite image to your Pictures folder?",
    ):
        final_name = f"satmap_{lat:.5f}_{lng:.5f}.jpg"
        final_path = safe_write_bytes(out_dir, ".jpg", jpeg_data,
                                      final_name=final_name)
        if final_path:
            messagebox.showinfo("Saved", f"Saved to:\n{final_path}")
    try:
        if temp_path.exists():
            os.unlink(temp_path)
    except OSError:
        pass


if __name__ == "__main__":
    main()

