"""Command-line interface for VeilLock.

    veillock encrypt --in frames.npy --out cipher.npz --mode private|broadcast|obfuscation
    veillock decrypt --in cipher.npz --out frames.npy --key ...
    veillock tether [--source camera|screen] [--mode obfuscation] [--device 0]
    veillock tether --obfuscation-off
    veillock tether --azos-accept --actor NAME
    veillock azos
    veillock apps
    veillock ui [--host 127.0.0.1] [--port 8761]
    veillock version
"""

from __future__ import annotations

import argparse
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veillock",
        description=(
            "VeilLock — consent-gated camera protection via AZ-OS "
            "(Aziel Eliab). Default: natural camera/video veil. "
            "Local UI: `veillock ui` at http://127.0.0.1:8761."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encrypt", help="Encrypt an RGB frame stack (.npy) to cipher.npz.")
    p_enc.add_argument("--in", dest="inp", required=True, help="Input frames.npy (N,H,W,3) uint8.")
    p_enc.add_argument("--out", dest="out", required=True, help="Output cipher.npz.")
    p_enc.add_argument(
        "--mode",
        required=True,
        choices=("private", "broadcast", "obfuscation"),
        help="Deployment mode.",
    )
    p_enc.add_argument(
        "--key",
        default=None,
        help="Optional 64-char hex session key (generated if omitted).",
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

    p_dec = sub.add_parser("decrypt", help="Decrypt cipher.npz to frames.npy.")
    p_dec.add_argument("--in", dest="inp", required=True, help="Input cipher.npz.")
    p_dec.add_argument("--out", dest="out", required=True, help="Output frames.npy.")
    p_dec.add_argument(
        "--key",
        default=None,
        help="64-char hex session key (root key; required for private/obfuscation).",
    )
    p_dec.add_argument(
        "--receiver-secret",
        default=None,
        help="Hex receiver secret (unwraps the broadcast package key).",
    )

    p_doc = sub.add_parser("doctor", help="Self-check: pulse, loopback, numpy. No network.")
    p_doc.add_argument("--json", action="store_true", dest="as_json", help="Print doctor results as JSON.")
    sub.add_parser("version", help="Print the VeilLock version and exit.")

    p_ui = sub.add_parser("ui", aliases=["serve"], help="Run the localhost UI (127.0.0.1).")
    p_ui.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1).")
    p_ui.add_argument("--port", type=int, default=8761, help="Bind port (default 8761).")

    p_tether = sub.add_parser(
        "tether",
        help="Pipe YOUR camera/video through VeilLock. Default: natural veil.",
    )
    p_tether.add_argument(
        "--source",
        choices=("camera", "screen"),
        default="camera",
        help="Local source: this machine's camera (default) or this machine's screen.",
    )
    p_tether.add_argument(
        "--mode",
        choices=("obfuscation", "private", "broadcast"),
        default="obfuscation",
        help="Seal mode (default obfuscation). Public feed stays veiled unless you lift it.",
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
        help="How to pick VeilLock in Zoom, Skype, FaceTime (Mac), Meet, Teams.",
    )
    p_azos = sub.add_parser("azos", help="Show the AZ-OS consent hook status.")
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
        raise SystemExit(f"error: {label} must be hex: {exc}") from exc
    if expected_len is not None and len(raw) != expected_len:
        raise SystemExit(f"error: {label} must be {expected_len} bytes ({expected_len * 2} hex chars)")
    return raw


def _load_frames(path: str) -> np.ndarray:
    try:
        arr = np.load(path)
    except FileNotFoundError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"error: failed to read frames: {exc}") from exc
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    if arr.ndim == 3 and arr.shape[-1] == 3:
        arr = arr[None, ...]
    if arr.ndim != 4 or arr.shape[-1] != 3:
        raise SystemExit("error: frames.npy must have shape (N,H,W,3) or (H,W,3) uint8")
    return arr


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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
        except ValueError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        return 0

    if args.cmd == "apps":
        from veillock.tether import APPS_GUIDE

        sys.stdout.write(APPS_GUIDE)
        if not APPS_GUIDE.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    if args.cmd == "azos":
        import json

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
            sys.stdout.write(
                f"VeilLock AZ-OS hook  veil={payload['veil']}  "
                f"reason={payload['reason']}\n"
                f"obfuscation_on={payload['obfuscation_on']}  "
                f"call_accepted={payload['call_accepted']}\n"
                "You control the veil. Author: Aziel Eliab.\n"
            )
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
            sys.stderr.write(f"error: {exc}\n")
            return 2
        sys.stdout.write(f"session_key={session_key.hex()}\n")
        if receiver_secret is not None:
            sys.stdout.write(f"receiver_secret={receiver_secret.hex()}\n")
        sys.stdout.write(f"frames={frames.shape[0]} mode={mode.value} out={args.out}\n")
        return 0

    if args.cmd == "decrypt":
        try:
            stream = load_cipher_npz(args.inp)
        except FileNotFoundError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"error: failed to read cipher package: {exc}\n")
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
                sys.stderr.write("error: decrypt requires --key or --receiver-secret\n")
                return 2
            out = session.decrypt_frames(stream)
        except (HaltedError, DecryptError, ValueError) as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 1
        np.save(args.out, out)
        sys.stdout.write(f"frames={out.shape[0]} out={args.out}\n")
        return 0

    parser.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
