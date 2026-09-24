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
        help="How to pick VeilLock in a call app.",
        description="How to pick VeilLock in Zoom, Skype, FaceTime (Mac), Meet, and Teams.",
        epilog="Example: veillock apps",
        **common,
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
