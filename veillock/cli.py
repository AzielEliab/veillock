"""Command-line interface for VeilLock.

    veillock
    veillock ui [--host 127.0.0.1] [--port 8761]
    veillock tether [--source camera|screen] [--mode obfuscation] [--device 0]
    veillock tether --obfuscation-off
    veillock tether --azos-accept --actor NAME
    veillock azos
    veillock apps
    veillock doctor
    veillock encrypt --in frames.npy --out cipher.npz --mode private|broadcast|obfuscation
    veillock decrypt --in cipher.npz --out frames.npy --key ...
    veillock wrap --feed scramble --azos-accept --actor NAME
    veillock receive --in captured.npy --out picture.npy --key HEX
    veillock record --in frames.npy --out clip.veilrec --key HEX
    veillock play --in clip.veilrec --out frames.npy --key HEX
    veillock keygen
    veillock version
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from typing import Sequence

import numpy as np

from veillock import __version__
from veillock.crypto import DecryptError
from veillock.engine import (
    VeilLockSession,
    load_cipher_npz,
    save_cipher_npz,
    session_from_wrapped,
)
from veillock.modes import Mode
from veillock.pulse import HaltedError

WELCOME = """\
VeilLock keeps your camera veiled until you lift it.

You lift the veil by turning obfuscation off, or by accepting a call through AZ-OS.

Next:
  veillock ui       Open the local app
  veillock doctor   Check this computer
  veillock tether   Send your camera through VeilLock
  veillock --help   See every command

Author: Aziel Eliab
"""

ROOT_HELP = f"""\
veillock — keep your camera veiled until you lift it

usage:
  veillock
  veillock <command> [options]
  veillock ui

VeilLock keeps your camera veiled until you lift it.
Author: Aziel Eliab. Version {__version__}.

Common commands:
  ui (serve)    Open the local app at http://127.0.0.1:8761
  tether        Send your camera through VeilLock
  azos          Show whether the veil is on
  doctor        Check that this computer is ready
  apps          How to pick VeilLock in Zoom, Skype, FaceTime, Meet, Teams
  version       Print the version

Advanced:
  encrypt       Seal an RGB frame file (.npy) to cipher.npz
  decrypt       Open a sealed file back to frames

Run veillock <command> --help for that command's options.
Machine-readable output: add --json on doctor, azos, encrypt, and decrypt.

Examples:
  veillock
  veillock ui
  veillock doctor
  veillock tether
  veillock --help
"""


class VeilParser(argparse.ArgumentParser):
    """Root help reads like git/npm. Misuse prints a reason and a next step."""

    veil_root: bool = False

    def format_help(self) -> str:
        if self.veil_root:
            return ROOT_HELP
        return super().format_help()

    def error(self, message: str) -> None:
        self.exit(2, _plain_error(self.prog, message) + "\n")


def _plain_error(prog: str, message: str) -> str:
    choice = re.search(r"invalid choice: '([^']+)'", message)
    if choice:
        bad = choice.group(1)
        return f'Unknown command "{bad}". Try: veillock ui   or   veillock --help'
    if message.startswith("unrecognized arguments"):
        extra = message.split(":", 1)[-1].strip()
        return f"Unknown option {extra}. Try: {prog} --help"
    if "required" in message:
        if prog.endswith(" encrypt"):
            return (
                "Encrypt needs an input file, an output file, and a mode. "
                "Try: veillock encrypt --in frames.npy --out cipher.npz --mode private"
            )
        if prog.endswith(" decrypt"):
            return (
                "Decrypt needs an input file and an output file. "
                "Try: veillock decrypt --in cipher.npz --out frames.npy --key <hex>"
            )
        if prog.endswith(" ui") or prog.endswith(" serve"):
            return "Try: veillock ui"
        return f"Missing required options. Try: {prog} --help"
    if message.startswith("argument"):
        return f"{message}. Try: {prog} --help"
    return f"{message}. Try: {prog} --help"


def _die(text: str, code: int = 2) -> None:
    sys.stderr.write(text.rstrip() + "\n")
    raise SystemExit(code)


def _build_parser() -> VeilParser:
    parser = VeilParser(prog="veillock")
    parser.veil_root = True
    sub = parser.add_subparsers(dest="cmd", required=False, parser_class=VeilParser)
    common = {"formatter_class": argparse.RawDescriptionHelpFormatter}

    p_enc = sub.add_parser(
        "encrypt",
        help="Seal an RGB frame file.",
        description="Seal an RGB frame file (.npy) to cipher.npz.",
        epilog="Example: veillock encrypt --in frames.npy --out cipher.npz --mode private",
        **common,
    )
    p_enc.add_argument("--in", dest="inp", required=True, help="Input frames.npy (N,H,W,3) uint8.")
    p_enc.add_argument("--out", dest="out", required=True, help="Output cipher.npz.")
    p_enc.add_argument(
        "--mode",
        required=True,
        choices=("private", "broadcast", "obfuscation"),
        help="private, broadcast, or obfuscation.",
    )
    p_enc.add_argument(
        "--key",
        default=None,
        help="Optional 64-character hex session key (generated if omitted).",
    )
    p_enc.add_argument(
        "--receiver-secret",
        default=None,
        help="Hex receiver secret (broadcast mode; generated if omitted).",
    )
    p_enc.add_argument(
        "--rotation-interval",
        type=int,
        default=120,
        help="Forward-secure rotation period in frames (60–240, default 120).",
    )
    p_enc.add_argument("--json", action="store_true", dest="as_json", help="Print the result as JSON.")

    p_dec = sub.add_parser(
        "decrypt",
        help="Open a sealed frame file.",
        description="Open cipher.npz back to frames.npy.",
        epilog="Example: veillock decrypt --in cipher.npz --out frames.npy --key <hex>",
        **common,
    )
    p_dec.add_argument("--in", dest="inp", required=True, help="Input cipher.npz.")
    p_dec.add_argument("--out", dest="out", required=True, help="Output frames.npy.")
    p_dec.add_argument(
        "--key",
        default=None,
        help="64-character hex session key (required for private and obfuscation).",
    )
    p_dec.add_argument(
        "--receiver-secret",
        default=None,
        help="Hex receiver secret (unwraps the broadcast package key).",
    )
    p_dec.add_argument("--json", action="store_true", dest="as_json", help="Print the result as JSON.")

    p_doc = sub.add_parser(
        "doctor",
        help="Check that this computer is ready.",
        description="Check pulse, loopback, and the AZ-OS veil. No network.",
        epilog="Example: veillock doctor",
        **common,
    )
    p_doc.add_argument("--json", action="store_true", dest="as_json", help="Print doctor results as JSON.")
    sub.add_parser(
        "version",
        help="Print the version.",
        description="Print the VeilLock version.",
        epilog="Example: veillock version",
        **common,
    )

    p_ui = sub.add_parser(
        "ui",
        aliases=["serve"],
        help="Open the local app.",
        description="Open the local app on this computer (127.0.0.1).",
        epilog="Example: veillock ui",
        **common,
    )
    p_ui.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1).")
    p_ui.add_argument("--port", type=int, default=8761, help="Bind port (default 8761).")

    p_tether = sub.add_parser(
        "tether",
        help="Send your camera through VeilLock.",
        description="Send your camera or screen through VeilLock. The public feed stays veiled until you lift it.",
        epilog=(
            "Examples:\n"
            "  veillock tether\n"
            "  veillock tether --obfuscation-off\n"
            "  veillock tether --azos-accept --actor \"your name\""
        ),
        **common,
    )
    p_tether.add_argument(
        "--source",
        choices=("camera", "screen"),
        default="camera",
        help="This machine's camera (default) or this machine's screen.",
    )
    p_tether.add_argument(
        "--mode",
        choices=("obfuscation", "private", "broadcast"),
        default="obfuscation",
        help="Seal mode (default obfuscation). The public feed stays veiled until you lift it.",
    )
    p_tether.add_argument(
        "--device",
        default=0,
        type=int,
        help="OpenCV camera index (default 0). Ignored for --source screen.",
    )
    p_tether.add_argument(
        "--trusted",
        action="store_true",
        help="Lift the veil and send the trusted local decode (same as --obfuscation-off).",
    )
    p_tether.add_argument(
        "--obfuscation-off",
        action="store_true",
        dest="obfuscation_off",
        help="You turned obfuscation off. Lifts the camera veil.",
    )
    p_tether.add_argument(
        "--azos-accept",
        action="store_true",
        dest="azos_accept",
        help="You accepted a call through AZ-OS. Lifts the camera veil.",
    )
    p_tether.add_argument(
        "--actor",
        default="",
        help="Named actor for the AZ-OS call-accept receipt (you).",
    )
    p_tether.add_argument("--width", type=int, default=640, help="Virtual camera width (default 640).")
    p_tether.add_argument("--height", type=int, default=480, help="Virtual camera height (default 480).")
    p_tether.add_argument("--fps", type=float, default=15, help="Virtual camera fps (default 15).")

    sub.add_parser(
        "apps",
        help="How to pick VeilLock in a desktop call app, OBS, or a browser.",
        description="How to pick VeilLock in Zoom, Skype, FaceTime (Mac), Meet, and Teams.",
        epilog="Example: veillock apps",
        **common,
    )
    p_compat = sub.add_parser(
        "compat",
        help="Show the app coverage registry, or detect one running app. Not a market-share ranking.",
    )
    p_compat.add_argument("--list", action="store_true", help="Print every built-in profile.")
    p_compat.add_argument("--detect", action="store_true", help="Resolve one process, bundle, or URL.")
    p_compat.add_argument("--process", default=None, help="Process name, for example Zoom.exe.")
    p_compat.add_argument("--platform", default=None, help="linux, windows, darwin, ios, android, chromium, firefox, or safari.")
    p_compat.add_argument("--bundle", default=None, help="Bundle id, for example com.apple.facetime.")
    p_compat.add_argument("--url", default=None, help="Page URL, for example https://meet.google.com/abc.")
    p_compat.add_argument("--vcam", action="store_true", help="Treat the Windows 11 registrar as running. Does not register a camera.")
    p_compat.add_argument("--v4l2", action="store_true", help="This process opens /dev/video* itself.")
    p_compat.add_argument("--sandboxed", action="store_true", help="Flatpak, Snap, or a portal sandbox. Not engulfed.")
    p_compat.add_argument(
        "--capture",
        default=None,
        choices=("unknown", "v4l2", "pipewire", "portal", "flatpak", "snap", "media-foundation", "directshow", "avfoundation", "getusermedia"),
        help="How this app opens the camera. This outranks the process name.",
    )
    p_compat.add_argument("--windows-build", dest="windows_build", type=int, default=None, help="Windows build number. Below 22000 registers nothing.")

    p_join = sub.add_parser(
        "join",
        help="One report for a meeting link. Does not join the call or register a camera.",
    )
    p_join.add_argument("url", help="Join link, for example a Teams, Meet, Zoom, or Webex URL.")
    p_join.add_argument("--platform", default=None)
    p_join.add_argument("--process", default=None)
    p_join.add_argument(
        "--capture",
        default=None,
        choices=("unknown", "v4l2", "pipewire", "portal", "flatpak", "snap", "media-foundation", "directshow", "avfoundation", "getusermedia"),
    )
    p_join.add_argument("--windows-build", dest="windows_build", type=int, default=None)
    p_join.add_argument("--vcam", action="store_true")
    p_join.add_argument("--v4l2", action="store_true")
    p_join.add_argument("--sandboxed", action="store_true")

    p_wrap = sub.add_parser(
        "wrap",
        help="Veil or scramble the camera for any app that can select it. Not AES on the call path.",
    )
    p_wrap.add_argument("--source", choices=("camera", "screen"), default="camera")
    p_wrap.add_argument("--frames", default=None, help="Offline RGB .npy instead of a camera.")
    p_wrap.add_argument(
        "--feed",
        choices=("scramble", "veil", "plaintext"),
        default="scramble",
        help="Public video after you lift the veil. scramble is not AES-256-GCM.",
    )
    p_wrap.add_argument(
        "--mic",
        action="store_true",
        help=(
            "Feed a virtual microphone. Linux creates VeilLock Microphone via "
            "pactl. macOS feeds BlackHole if installed. Windows feeds VB-Cable "
            "if installed. Call audio is not AES-256-GCM."
        ),
    )
    p_wrap.add_argument(
        "--audio-feed",
        dest="audio_feed",
        choices=("veil", "auto", "plaintext", "scramble", "off"),
        default=None,
        help=(
            "Public audio. Default with --mic is auto: comfort noise until you "
            "lift the veil, then the microphone, or scramble if you ask for it. "
            "Not AES-256-GCM."
        ),
    )
    p_wrap.add_argument("--audio-in", dest="audio_in", default=None, help="PCM int16 .npy from the mic.")
    p_wrap.add_argument("--audio-out", dest="audio_out", default=None, help="Write the public PCM .npy.")
    p_wrap.add_argument("--preview-out", dest="preview_out", default=None, help="Write public frames .npy (no virtual camera).")
    p_wrap.add_argument("--record", default=None, help="AES-256-GCM .veilrec of the real frames. The call app does not get this file.")
    p_wrap.add_argument("--mode", choices=("private", "broadcast", "obfuscation"), default="private")
    p_wrap.add_argument("--device", default=0, type=int)
    p_wrap.add_argument("--key", default=None, help="64-char hex call key (scramble + local recording).")
    p_wrap.add_argument("--receiver-secret", dest="receiver_secret", default=None)
    p_wrap.add_argument("--x25519-private", dest="x25519_private", default=None)
    p_wrap.add_argument("--peer-public", dest="peer_public", default=None)
    p_wrap.add_argument("--obfuscation-off", action="store_true", dest="obfuscation_off")
    p_wrap.add_argument("--azos-accept", action="store_true", dest="azos_accept")
    p_wrap.add_argument("--actor", default="")
    p_wrap.add_argument("--width", type=int, default=640)
    p_wrap.add_argument("--height", type=int, default=480)
    p_wrap.add_argument("--fps", type=float, default=15)
    p_wrap.add_argument("--rotation-interval", dest="rotation_interval", type=int, default=120)
    p_wrap.add_argument("--max-frames", dest="max_frames", type=int, default=None)

    p_mic = sub.add_parser(
        "mic",
        help="Start or stop the virtual microphone. Call audio is not AES-256-GCM.",
    )
    p_mic.add_argument("action", choices=("status", "start", "stop"))
    p_mic.add_argument(
        "--scramble",
        action="store_true",
        help="When the veil is lifted, send a PCM scramble instead of the microphone.",
    )

    p_engulf = sub.add_parser(
        "engulf",
        help="Start an app so a direct /dev/video open receives VeilLock. Refuses platforms that cannot be wrapped.",
    )
    p_engulf.add_argument("app", nargs=argparse.REMAINDER, help="Command to start, after --.")
    p_engulf.add_argument("--video", default="/dev/video10", help="VeilLock V4L2 device to expose as the camera.")
    p_engulf.add_argument("--record", default=None, help="Seal what you send to an AES-256-GCM .veilrec before launch.")
    p_engulf.add_argument("--key", default=None, help="64-char hex key for --record. Not stored in the file.")
    p_engulf.add_argument("--frames", default=None, help="RGB .npy to seal when recording from engulf.")
    p_engulf.add_argument("--audio-in", dest="audio_in", default=None, help="PCM .npy to seal when recording from engulf.")

    p_link = sub.add_parser(
        "link",
        help="AES-256-GCM encoded frames between two VeilLock users. Not the call app's stream.",
    )
    p_link.add_argument("--listen", default=None, help="host:port to receive on.")
    p_link.add_argument("--connect", default=None, help="host:port to send to.")
    p_link.add_argument("--frames", default=None, help="RGB .npy to encode and send.")
    p_link.add_argument("--out", default=None, help="Where to write decrypted RGB .npy.")
    p_link.add_argument("--key", required=True, help="64-char hex E2E key.")
    p_link.add_argument("--lifted", action="store_true", help="Seal the camera. Omit to seal a veil instead.")

    p_recv = sub.add_parser(
        "receive",
        help="Unveil a captured call stack with the out-of-band key. Not an AES decrypt.",
    )
    p_recv.add_argument("--in", dest="inp", required=True)
    p_recv.add_argument("--out", dest="out", default=None, help="Plaintext export path. Requires --export.")
    p_recv.add_argument("--record", default=None, help="Seal the unveiled frames to an AES-256-GCM .veilrec.")
    p_recv.add_argument(
        "--export",
        action="store_true",
        help="Write plaintext. This leaves VeilLock's protection. Off unless you pass this flag.",
    )
    p_recv.add_argument("--key", required=True, help="64-char hex call key.")
    p_recv.add_argument("--audio-in", dest="audio_in", default=None)
    p_recv.add_argument("--audio-out", dest="audio_out", default=None)
    p_recv.add_argument("--epoch", type=int, default=0, help="Epoch for audio only. Video reads its own sync strip.")

    p_rec = sub.add_parser("record", help="Seal video and/or audio to an AES-256-GCM .veilrec. Nothing plaintext is written.")
    p_rec.add_argument("--in", dest="inp", default=None, help="RGB .npy. Omit for audio-only.")
    p_rec.add_argument("--out", dest="out", required=True)
    p_rec.add_argument("--key", default=None)
    p_rec.add_argument("--audio-in", dest="audio_in", default=None, help="PCM int16 .npy. Omit for video-only.")
    p_rec.add_argument("--rotation-interval", dest="rotation_interval", type=int, default=120)

    p_play = sub.add_parser("play", help="Decrypt a .veilrec in memory. Wrong key opens nothing. Plaintext export is off.")
    p_play.add_argument("--in", dest="inp", required=True)
    p_play.add_argument("--out", dest="out", default=None, help="Plaintext video export. Requires --export.")
    p_play.add_argument("--key", required=True)
    p_play.add_argument("--audio-out", dest="audio_out", default=None, help="Plaintext PCM export. Requires --export.")
    p_play.add_argument(
        "--export",
        action="store_true",
        help="Write plaintext to --out or --audio-out. This leaves VeilLock's protection.",
    )

    sub.add_parser("keygen", help="Print a pre-shared call key and an X25519 keypair.")
    p_agree = sub.add_parser("agree", help="Derive the call key from your X25519 private key and the peer public key.")
    p_agree.add_argument("--private", required=True, help="64-char hex X25519 private key.")
    p_agree.add_argument("--peer-public", dest="peer_public", required=True)
    p_agree.add_argument(
        "--e2e",
        action="store_true",
        help="Derive the VeilLock link key (AES-256-GCM media). Omit this for the scramble key, which is not AES.",
    )
    p_azos = sub.add_parser(
        "azos",
        help="Show whether the veil is on.",
        description="Show the AZ-OS consent hook. You control the veil.",
        epilog="Example: veillock azos",
        **common,
    )
    p_azos.add_argument("--json", action="store_true", dest="as_json", help="Print hook status as JSON.")
    p_azos.add_argument(
        "--accept",
        action="store_true",
        help="Record that you accepted a call through AZ-OS.",
    )
    p_azos.add_argument("--end", action="store_true", help="End the accepted call and re-veil.")
    p_azos.add_argument(
        "--obfuscation-off",
        action="store_true",
        dest="obfuscation_off",
        help="Turn obfuscation off (you).",
    )
    p_azos.add_argument(
        "--obfuscation-on",
        action="store_true",
        dest="obfuscation_on",
        help="Turn obfuscation back on (default).",
    )
    p_azos.add_argument("--actor", default="", help="Named actor for call-accept.")
    return parser


def _parse_hex(label: str, value: str, expected_len: int | None = None) -> bytes:
    try:
        raw = bytes.fromhex(value.strip())
    except ValueError as exc:
        _die(f"The {label} must be hex ({exc}). Try: veillock --help")
    if expected_len is not None and len(raw) != expected_len:
        _die(
            f"The {label} must be {expected_len} bytes ({expected_len * 2} hex characters). "
            "Try: veillock --help"
        )
    return raw


def _load_frames(path: str) -> np.ndarray:
    try:
        arr = np.load(path)
    except FileNotFoundError:
        _die(f"Could not find {path}. Try: check the path, then veillock encrypt --help")
    except Exception as exc:  # noqa: BLE001
        _die(f"Could not read frames ({exc}). Try: veillock encrypt --help")
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    if arr.ndim == 3 and arr.shape[-1] == 3:
        arr = arr[None, ...]
    if arr.ndim != 4 or arr.shape[-1] != 3:
        _die(
            "Frames must be uint8 RGB with shape (N,H,W,3) or (H,W,3). "
            "Try: veillock encrypt --help"
        )
    return arr


def _azos_human(payload: dict) -> str:
    veil = payload["veil"]
    if veil == "lifted":
        sentence = "The veil is lifted."
    else:
        sentence = "The veil is on. Your camera stays protected until you lift it."
    return (
        "VeilLock AZ-OS hook\n"
        f"veil={veil}\n"
        f"{sentence}\n"
        f"Reason: {payload['reason']}\n"
        f"obfuscation_on={payload['obfuscation_on']}  "
        f"call_accepted={payload['call_accepted']}\n"
        "Author: Aziel Eliab\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv:
        sys.stdout.write(WELCOME)
        return 0
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None or code == 0:
            return 0
        if isinstance(code, int):
            return code
        return 2

    if args.cmd is None:
        sys.stdout.write(WELCOME)
        return 0

    if args.cmd == "doctor":
        from veillock.doctor import doctor_cli

        return doctor_cli(as_json=args.as_json)

    if args.cmd == "version":
        sys.stdout.write(f"veillock {__version__}\n")
        return 0

    if args.cmd in ("ui", "serve"):
        from veillock.ui import serve

        try:
            serve(host=args.host, port=args.port)
        except ValueError:
            sys.stderr.write("VeilLock stays on this computer (127.0.0.1). Try: veillock ui\n")
            return 2
        return 0

    if args.cmd == "apps":
        from veillock.tether import APPS_GUIDE

        sys.stdout.write(APPS_GUIDE)
        if not APPS_GUIDE.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    if args.cmd in ("compat", "join"):
        from veillock.coverage import coverage_guide_text
        from veillock.surfaces import describe

        if args.cmd == "join" or args.detect or args.process or args.bundle or args.url:
            import os
            try:
                text = describe(
                    getattr(args, "process", None),
                    platform=args.platform,
                    bundle_id=getattr(args, "bundle", None),
                    url=getattr(args, "url", None),
                    have_vcam=True if args.vcam else None,
                    opens_v4l2=bool(args.v4l2),
                    sandboxed=bool(args.sandboxed),
                    capture=args.capture,
                    windows_build=args.windows_build,
                    environ=dict(os.environ),
                )
            except ValueError as exc:
                sys.stderr.write(f"error: {exc}\n")
                return 2
            sys.stdout.write(text)
            return 0
        sys.stdout.write(coverage_guide_text())
        return 0

    if args.cmd == "azos":
        from veillock.azos import HOOK

        if args.obfuscation_off:
            HOOK.set_obfuscation(False)
        if args.obfuscation_on:
            HOOK.set_obfuscation(True)
        if args.accept:
            HOOK.accept_call(actor=args.actor or "user")
        if args.end:
            HOOK.end_call()
        payload = HOOK.status()
        if args.as_json:
            sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(_azos_human(payload))
        return 0

    if args.cmd == "tether":
        from veillock.tether import run_from_args

        return run_from_args(args)

    if args.cmd == "wrap":
        from veillock.wrap import run_from_args as wrap_from_args

        return wrap_from_args(args)

    if args.cmd == "mic":
        from veillock.mic import MIC_RUNTIME

        action = str(args.action)
        if action == "start":
            payload = MIC_RUNTIME.start(scramble_when_lifted=bool(args.scramble))
        elif action == "stop":
            payload = MIC_RUNTIME.stop()
        else:
            payload = MIC_RUNTIME.status()
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0 if payload.get("ok", True) and not payload.get("error") else 2

    if args.cmd == "keygen":
        from veillock.callkeys import generate_x25519, random_psk
        from veillock.honesty import CALL_VIDEO

        psk = random_psk()
        priv, pub = generate_x25519()
        sys.stdout.write(f"psk={psk.hex()}\n")
        sys.stdout.write(f"x25519_private={priv.hex()}\n")
        sys.stdout.write(f"x25519_public={pub.hex()}\n")
        sys.stdout.write(CALL_VIDEO + "\n")
        sys.stdout.write("The psk seals a local AES-256-GCM recording and drives the call scramble. The scramble is not AES-256-GCM.\n")
        return 0

    if args.cmd == "agree":
        from veillock.callkeys import agree_e2e, agree_x25519

        try:
            private = _parse_hex("private", args.private, 32)
            peer = _parse_hex("peer-public", args.peer_public, 32)
            shared = agree_e2e(private, peer) if args.e2e else agree_x25519(private, peer)
        except ValueError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        sys.stdout.write(f"session_key={shared.hex()}\n")
        if args.e2e:
            sys.stdout.write(
                "Same 32 bytes on both peers. This key is for veillock link and the browser "
                "encoded frames: AES-256-GCM. It is not the scramble key. Both ends need VeilLock.\n"
            )
        else:
            sys.stdout.write("Same 32 bytes on both peers. Call video that uses it is a scramble, not AES-256-GCM. A veillock record file that uses it is AES-256-GCM.\n")
        return 0

    if args.cmd == "engulf":
        from veillock.engulf import run_engulf

        app = [part for part in (args.app or []) if part != "--"]
        if not app:
            sys.stderr.write("error: veillock engulf -- <app> [args]\n")
            return 2
        if args.record:
            if not args.key:
                sys.stderr.write("error: --record needs --key. The key is not stored in the file.\n")
                return 2
            if not args.frames and not args.audio_in:
                sys.stderr.write("error: --record needs --frames, --audio-in, or both\n")
                return 2
            from veillock.record import seal_recording

            frames = _load_frames(args.frames) if args.frames else np.zeros((0, 1, 1, 3), dtype=np.uint8)
            pcm = np.load(args.audio_in) if args.audio_in else None
            try:
                seal_recording(args.record, frames, _parse_hex("key", args.key, 32), pcm=pcm)
            except (HaltedError, ValueError) as exc:
                sys.stderr.write(f"error: {exc}\n")
                return 2
            sys.stdout.write(f"record={args.record} crypto=AES-256-GCM\n")
        return run_engulf(app, video_device=str(args.video))

    if args.cmd == "link":
        from veillock.e2e import (
            KIND_VIDEO,
            EncodedChannel,
            decode_picture,
            encode_picture,
            open_encoded,
            recv_blobs,
            send_blobs,
        )
        import socket

        try:
            key = _parse_hex("key", args.key, 32)
        except ValueError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        if bool(args.listen) == bool(args.connect):
            sys.stderr.write("error: pass exactly one of --listen or --connect\n")
            return 2

        def _hostport(text: str) -> tuple[str, int]:
            host, _, port = str(text).rpartition(":")
            if not host or not port.isdigit():
                raise ValueError("address must be host:port")
            return host, int(port)

        try:
            if args.connect:
                if not args.frames:
                    sys.stderr.write("error: --connect needs --frames\n")
                    return 2
                frames = _load_frames(args.frames)
                channel = EncodedChannel(key)
                blobs = []
                for frame in frames:
                    picture = frame if args.lifted else np.zeros_like(frame)
                    blobs.append(channel.seal(encode_picture(picture), KIND_VIDEO))
                host, port = _hostport(args.connect)
                sock = socket.create_connection((host, port), timeout=10)
                try:
                    send_blobs(sock, blobs)
                finally:
                    sock.close()
                sys.stdout.write(
                    f"sent={len(blobs)} aes=AES-256-GCM lifted={bool(args.lifted)} "
                    "observer_sees=ciphertext\n"
                )
                return 0
            host, port = _hostport(args.listen)
            if not args.out:
                sys.stderr.write("error: --listen needs --out\n")
                return 2
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(1)
            sys.stdout.write(f"listening {host}:{port}\n")
            sys.stdout.flush()
            conn, _addr = srv.accept()
            try:
                blobs = recv_blobs(conn)
            finally:
                conn.close()
                srv.close()
            from veillock.record import seal_recording

            opened = []
            for blob in blobs:
                payload, _kind = open_encoded(blob, key)
                opened.append(decode_picture(payload))
            if not opened:
                sys.stderr.write("error: link received no frames\n")
                return 2
            seal_recording(args.out, np.stack(opened, axis=0), key)
            sys.stdout.write(
                f"frames={len(opened)} record={args.out} aes=AES-256-GCM "
                "plaintext_file=no\n"
            )
            return 0
        except (OSError, ValueError, HaltedError, DecryptError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2

    if args.cmd == "receive":
        from veillock.wrap import receive_audio, receive_stack

        frames = _load_frames(args.inp)
        try:
            key = _parse_hex("key", args.key, 32)
            out, results = receive_stack(frames, key)
        except (ValueError, HaltedError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        kinds = ",".join(r.kind for r in results)
        authorized = sum(1 for r in results if r.authorized)
        received_pcm = None
        if args.audio_in and args.record:
            received_pcm = receive_audio(np.load(args.audio_in), key, epoch=int(args.epoch))
        if args.record:
            from veillock.record import seal_recording

            seal_recording(args.record, out, key, pcm=received_pcm)
            sys.stdout.write(f"record={args.record} crypto=AES-256-GCM frames={out.shape[0]}\n")
        if args.out or args.audio_out:
            if not args.export:
                sys.stderr.write(
                    "error: plaintext export is off. Pass --export and the key. This leaves VeilLock's protection.\n"
                )
                return 2
            from veillock.honesty import EXPORT_LEAVES

            sys.stdout.write(EXPORT_LEAVES + "\n")
        if args.out:
            np.save(args.out, out)
            sys.stdout.write(
                f"frames={out.shape[0]} authorized={authorized} kinds={kinds} export={args.out}\n"
            )
        else:
            sys.stdout.write(f"frames={out.shape[0]} authorized={authorized} kinds={kinds} kept_in_memory=1\n")
        sys.stdout.write(results[0].note + "\n")
        if args.audio_in and args.audio_out:
            if not args.export:
                sys.stderr.write("error: --audio-out requires --export\n")
                return 2
            pcm = np.load(args.audio_in)
            unveiled = receive_audio(pcm, key, epoch=int(args.epoch))
            np.save(args.audio_out, unveiled)
            sys.stdout.write(f"audio_out={args.audio_out} note=pcm-block-scramble-not-aes\n")
        elif args.audio_in and not args.record:
            sys.stderr.write("error: --audio-in requires --record or --export --audio-out\n")
            return 2
        return 0

    if args.cmd == "record":
        from veillock.honesty import LOCAL_RECORDING
        from veillock.record import seal_recording

        if not args.inp and not args.audio_in:
            sys.stderr.write("error: record needs --in, --audio-in, or both\n")
            return 2
        frames = _load_frames(args.inp) if args.inp else np.zeros((0, 1, 1, 3), dtype=np.uint8)
        session_key = _parse_hex("key", args.key, 32) if args.key else secrets.token_bytes(32)
        pcm = np.load(args.audio_in) if args.audio_in else None
        try:
            seal_recording(
                args.out,
                frames,
                session_key,
                pcm=pcm,
                rotation_interval=args.rotation_interval,
            )
        except (HaltedError, ValueError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        sys.stdout.write(f"session_key={session_key.hex()}\n")
        sys.stdout.write(f"crypto=AES-256-GCM out={args.out}\n")
        sys.stdout.write(LOCAL_RECORDING + "\n")
        return 0

    if args.cmd == "play":
        from veillock.crypto import DecryptError as _DecryptError
        from veillock.record import play_recording

        try:
            played = play_recording(args.inp, _parse_hex("key", args.key, 32))
        except FileNotFoundError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        except (HaltedError, _DecryptError, ValueError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 1
        pcm_n = 0 if played.pcm is None else int(played.pcm.shape[0])
        sys.stdout.write(
            f"frames={played.frames.shape[0]} audio_samples={pcm_n} crypto=AES-256-GCM in_memory=1\n"
        )
        sys.stdout.write(played.note + "\n")
        if args.out or args.audio_out:
            if not args.export:
                sys.stderr.write(
                    "error: plaintext export is off. Pass --export and the key. This leaves VeilLock's protection.\n"
                )
                return 2
            from veillock.honesty import EXPORT_LEAVES

            sys.stdout.write(EXPORT_LEAVES + "\n")
            if args.out:
                np.save(args.out, played.frames)
                sys.stdout.write(f"export={args.out}\n")
            if args.audio_out:
                np.save(args.audio_out, played.pcm if played.pcm is not None else np.zeros((0,), dtype=np.int16))
                sys.stdout.write(f"audio_export={args.audio_out}\n")
        return 0

    if args.cmd == "encrypt":
        frames = _load_frames(args.inp)
        if args.key:
            session_key = _parse_hex("key", args.key, 32)
        else:
            session_key = secrets.token_bytes(32)
        receiver_secret = None
        mode = Mode.parse(args.mode)
        if mode is Mode.BROADCAST:
            if args.receiver_secret:
                receiver_secret = _parse_hex("receiver-secret", args.receiver_secret)
            else:
                receiver_secret = secrets.token_bytes(32)
        try:
            session = VeilLockSession(
                session_key=session_key,
                rotation_interval=args.rotation_interval,
                mode=mode,
                receiver_secret=receiver_secret,
            )
            stream = session.encrypt_frames(frames)
            save_cipher_npz(args.out, stream)
        except (HaltedError, ValueError) as exc:
            sys.stderr.write(f"{exc}\nNext: veillock doctor\n")
            return 2
        if args.as_json:
            payload = {
                "session_key": session_key.hex(),
                "frames": int(frames.shape[0]),
                "mode": mode.value,
                "out": args.out,
            }
            if receiver_secret is not None:
                payload["receiver_secret"] = receiver_secret.hex()
            sys.stdout.write(json.dumps(payload) + "\n")
        else:
            sys.stdout.write(f"session_key={session_key.hex()}\n")
            if receiver_secret is not None:
                sys.stdout.write(f"receiver_secret={receiver_secret.hex()}\n")
            sys.stdout.write(f"frames={frames.shape[0]} mode={mode.value} out={args.out}\n")
        return 0

    if args.cmd == "decrypt":
        try:
            stream = load_cipher_npz(args.inp)
        except FileNotFoundError:
            sys.stderr.write(
                f"Could not find {args.inp}. Try: check the path, then veillock decrypt --help\n"
            )
            return 2
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"Could not read the cipher package ({exc}). Try: veillock decrypt --help\n")
            return 2

        try:
            if args.receiver_secret and stream.wrapped_key:
                secret = _parse_hex("receiver-secret", args.receiver_secret)
                session = session_from_wrapped(
                    stream.wrapped_key,
                    secret,
                    rotation_interval=stream.rotation_interval,
                    mode=stream.mode,
                )
            elif args.key:
                session_key = _parse_hex("key", args.key, 32)
                extra = {}
                if stream.mode == Mode.BROADCAST.value and args.receiver_secret:
                    extra["receiver_secret"] = _parse_hex("receiver-secret", args.receiver_secret)
                session = VeilLockSession(
                    session_key=session_key,
                    rotation_interval=stream.rotation_interval,
                    mode=stream.mode,
                    **extra,
                )
            else:
                sys.stderr.write(
                    "Decrypt needs a key or a receiver secret. "
                    "Try: veillock decrypt --in cipher.npz --out frames.npy --key <hex>\n"
                )
                return 2
            out = session.decrypt_frames(stream)
        except (HaltedError, DecryptError, ValueError) as exc:
            sys.stderr.write(f"{exc}\nNext: check the key, then veillock decrypt --help\n")
            return 1
        np.save(args.out, out)
        if args.as_json:
            sys.stdout.write(json.dumps({"frames": int(out.shape[0]), "out": args.out}) + "\n")
        else:
            sys.stdout.write(f"frames={out.shape[0]} out={args.out}\n")
        return 0

    _die(f'Unknown command "{args.cmd}". Try: veillock ui   or   veillock --help')
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
