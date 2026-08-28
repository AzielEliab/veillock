"""Opt-in virtual-camera tether: YOUR camera/screen → VeilLock → call apps.

The user starts this feed. Zoom, Skype, desktop FaceTime, Meet, and Teams
then *choose* the virtual camera named VeilLock. This is not a MITM, not a
call interceptor, and not malware.

Default public feed is obfuscation (synthetic UI noise). PulseCheck must
PASS or the virtual camera receives obfuscation noise — never plaintext.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from typing import Any, Iterator, TextIO

import numpy as np

from veillock.engine import VeilLockSession
from veillock.modes import Mode, synthetic_ui_noise
from veillock.pulse import AlwaysPass, HaltedError, PhoenixError, PulseCheck
from veillock.sources import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    InstallError,
    open_source,
    resize_rgb,
)

DEVICE_NAME = "VeilLock"
DEFAULT_FPS = 15.0
DEFAULT_MODE = "obfuscation"
DEFAULT_SOURCE = "camera"

APPS_GUIDE = """\
VeilLock virtual camera
=======================

YOUR camera or screen only. VeilLock is not a Zoom/FaceTime interceptor,
not malware, and not a scraper of other apps' private buffers. The call
app must choose the camera named "VeilLock". VeilLock does not inject
into the call.

Install the optional extra, then start the tether:

  pip install 'veillock[tether]'
  veillock tether --source camera --mode obfuscation --device 0

Default mode is obfuscation: people on the call see synthetic UI noise,
not your plaintext camera. PulseCheck must PASS or the feed becomes
obfuscation noise (never plaintext). Private mode sends black/decoy
unless you pass --trusted (trusted local decode — still your choice).

Linux (v4l2loopback), once per boot if the VeilLock device is missing:

  sudo modprobe v4l2loopback devices=1 video_nr=10 card_label=VeilLock exclusive_caps=1

Zoom (desktop)
  Settings → Video → Camera → VeilLock

Skype (desktop)
  Settings → Audio & Video → Camera → VeilLock

FaceTime (Mac)
  Video menu → VeilLock
  Desktop FaceTime can select a third-party virtual camera.
  iPhone FaceTime cannot select a third-party virtual camera (Apple).

Google Meet (desktop browser)
  Meeting → More → Settings → Video → Camera → VeilLock
  Allow the browser to use the VeilLock device.

Microsoft Teams (desktop)
  Settings → Devices → Camera → VeilLock

Android / iOS
  iPhone FaceTime, Zoom iOS, and most mobile clients cannot select a
  third-party virtual camera. Use the desktop app (Mac FaceTime / Zoom /
  Skype / Meet / Teams).
"""


def _require_pyvirtualcam():
    try:
        import pyvirtualcam  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InstallError(
            "Virtual camera requires pyvirtualcam. Install with: pip install 'veillock[tether]'"
        ) from exc
    return pyvirtualcam


def _linux_v4l2_named(name: str = DEVICE_NAME) -> str | None:
    """Find a v4l2loopback node whose card label contains ``name``."""
    import glob

    needle = name.lower()
    for path in glob.glob("/sys/class/video4linux/video*/name"):
        try:
            with open(path, encoding="utf-8") as fh:
                label = fh.read().strip()
        except OSError:
            continue
        if needle in label.lower():
            node = path.rsplit("/", 2)[-2]
            return f"/dev/{node}"
    return None


def open_virtual_camera(
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: float = DEFAULT_FPS,
    name: str = DEVICE_NAME,
):
    """Open a virtual camera advertised as VeilLock when the backend allows it."""
    pvc = _require_pyvirtualcam()
    kwargs: dict[str, Any] = {
        "width": int(width),
        "height": int(height),
        "fps": float(fps),
    }
    fmt = getattr(getattr(pvc, "PixelFormat", None), "RGB", None)
    if fmt is not None:
        kwargs["fmt"] = fmt

    linux_dev = _linux_v4l2_named(name)
    attempts: list[dict[str, Any]] = []
    if linux_dev:
        attempts.append({"device": linux_dev})
    attempts.append({"device": name})
    attempts.append({})

    last_err: Exception | None = None
    for extra in attempts:
        try:
            return pvc.Camera(**kwargs, **extra)
        except TypeError:
            continue
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    hint = (
        " Could not open a virtual camera named VeilLock. "
        "On Linux load v4l2loopback with card_label=VeilLock "
        "(see `veillock apps`)."
    )
    if last_err is not None:
        raise RuntimeError(str(last_err) + hint) from last_err
    raise RuntimeError("pyvirtualcam.Camera rejected the VeilLock constructor." + hint)


@dataclass
class TetherConfig:
    source: str = DEFAULT_SOURCE
    mode: str = DEFAULT_MODE
    device: int | str = 0
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: float = DEFAULT_FPS
    trusted: bool = False
    session_key: bytes | None = None
    receiver_secret: bytes | None = None
    pulse: PulseCheck | None = None
    rotation_interval: int = 120
    max_frames: int | None = None
    rng: np.random.Generator | None = None


def emit_public_frame(
    session: VeilLockSession,
    frame: np.ndarray,
    *,
    trusted: bool = False,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Encrypt a caller-owned frame and choose pixels for the virtual camera.

    Without ``trusted``, the public feed is obfuscation decoy (obfuscation
    mode) or black (private/broadcast). Pulse halt / Phoenix → synthetic
    UI noise, never plaintext — even if ``trusted`` is set.
    """
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    h, w, c = int(src.shape[0]), int(src.shape[1]), int(src.shape[2])
    noise_rng = rng if rng is not None else np.random.default_rng()
    try:
        sealed, display = session.protect_frame(src)
    except (HaltedError, PhoenixError):
        return synthetic_ui_noise((h, w, c), noise_rng)
    if trusted:
        return np.ascontiguousarray(display, dtype=np.uint8)
    if session.mode is Mode.OBFUSCATION and sealed.decoy is not None:
        return np.ascontiguousarray(sealed.decoy, dtype=np.uint8)
    return np.zeros((h, w, c), dtype=np.uint8)


def halt_noise(width: int, height: int, rng: np.random.Generator | None = None) -> np.ndarray:
    """Obfuscation noise used when PCI fails and no plaintext may leave."""
    noise_rng = rng if rng is not None else np.random.default_rng()
    return synthetic_ui_noise((int(height), int(width), 3), noise_rng)


def run_tether(
    config: TetherConfig | None = None,
    *,
    frame_source: Iterator[np.ndarray] | None = None,
    virtual_cam: Any = None,
    stop_event: threading.Event | None = None,
    log: TextIO | None = None,
) -> int:
    """Grab → encrypt → write the public feed to the VeilLock virtual camera.

    ``frame_source`` and ``virtual_cam`` are injectable so tests never need
    a physical camera. Returns the number of frames sent.
    """
    cfg = config if config is not None else TetherConfig()
    mode = Mode.parse(cfg.mode)
    pulse: PulseCheck = cfg.pulse if cfg.pulse is not None else AlwaysPass()
    rng = cfg.rng if cfg.rng is not None else np.random.default_rng()
    out = log if log is not None else sys.stdout
    width, height = int(cfg.width), int(cfg.height)

    receiver_secret = cfg.receiver_secret
    if mode is Mode.BROADCAST and receiver_secret is None:
        import secrets as _secrets

        receiver_secret = _secrets.token_bytes(32)

    session = VeilLockSession(
        session_key=cfg.session_key,
        rotation_interval=cfg.rotation_interval,
        mode=mode,
        pulse=pulse,
        receiver_secret=receiver_secret,
        rng=rng,
    )

    owns_source = frame_source is None
    source: Any = frame_source
    if source is None:
        source = open_source(
            cfg.source,
            device=cfg.device,
            width=width,
            height=height,
            pulse=pulse,
        )

    owns_cam = virtual_cam is None
    cam = virtual_cam
    sent = 0
    try:
        if cam is None:
            cam = open_virtual_camera(width=width, height=height, fps=cfg.fps, name=DEVICE_NAME)
            enter = getattr(cam, "__enter__", None)
            if enter is not None:
                cam = enter()
        out.write(
            f"VeilLock tether  device={DEVICE_NAME}  "
            f"{width}x{height}@{cfg.fps:g}fps  "
            f"source={cfg.source}  mode={mode.value}  trusted={bool(cfg.trusted)}\n"
        )
        out.write(
            "Pick camera VeilLock in Zoom / Skype / desktop FaceTime / Meet / Teams. "
            "iPhone FaceTime cannot select a third-party virtual camera (Apple).\n"
        )
        if mode is Mode.BROADCAST and receiver_secret is not None:
            out.write(f"receiver_secret={receiver_secret.hex()}\n")
        out.write(f"session_key={session.current_key.hex()}\n")
        out.flush()

        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if cfg.max_frames is not None and sent >= cfg.max_frames:
                break
            try:
                frame = next(source)
            except StopIteration:
                break
            except HaltedError:
                public = halt_noise(width, height, rng)
            else:
                public = emit_public_frame(
                    session, frame, trusted=bool(cfg.trusted), rng=rng
                )
                public = resize_rgb(public, width, height)
            send = getattr(cam, "send", None)
            if send is None:
                raise RuntimeError("virtual camera has no send()")
            send(np.ascontiguousarray(public, dtype=np.uint8))
            sleeper = getattr(cam, "sleep_until_next_frame", None)
            if sleeper is not None:
                sleeper()
            sent += 1
    finally:
        if owns_cam and cam is not None:
            closer = getattr(cam, "__exit__", None)
            if closer is not None:
                closer(None, None, None)
            else:
                close = getattr(cam, "close", None)
                if close is not None:
                    close()
        if owns_source:
            close = getattr(source, "close", None)
            if close is not None:
                close()
    return sent


class TetherRuntime:
    """Background tether for the localhost UI (Start/Stop)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._error: str | None = None
        self._running = False
        self._cfg: TetherConfig | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "error": self._error,
                "source": None if self._cfg is None else self._cfg.source,
                "mode": None if self._cfg is None else self._cfg.mode,
                "trusted": None if self._cfg is None else self._cfg.trusted,
                "device_name": DEVICE_NAME,
            }

    def start(self, config: TetherConfig) -> dict[str, Any]:
        try:
            Mode.parse(config.mode)
            if str(config.source).strip().lower() not in ("camera", "screen"):
                raise ValueError("source must be camera or screen")
            _require_pyvirtualcam()
            if str(config.source).strip().lower() == "camera":
                from veillock.sources import _require_cv2

                _require_cv2()
        except (InstallError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "running": False, "device_name": DEVICE_NAME}
        with self._lock:
            if self._running:
                return {"ok": False, "error": "tether already running", **self.status()}
            self._stop = threading.Event()
            self._error = None
            self._cfg = config
            self._running = True
            stop = self._stop

            def _worker() -> None:
                try:
                    run_tether(config, stop_event=stop)
                except Exception as exc:  # noqa: BLE001
                    with self._lock:
                        self._error = str(exc)
                finally:
                    with self._lock:
                        self._running = False

            thread = threading.Thread(target=_worker, name="veillock-tether", daemon=True)
            self._thread = thread
            thread.start()
            return {"ok": True, **self.status()}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop.set()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._running = False
            return {"ok": True, **self.status()}


RUNTIME = TetherRuntime()


def run_from_args(args: Any) -> int:
    """CLI entry used by ``veillock tether``."""
    cfg = TetherConfig(
        source=str(getattr(args, "source", DEFAULT_SOURCE)),
        mode=str(getattr(args, "mode", DEFAULT_MODE)),
        device=getattr(args, "device", 0),
        width=int(getattr(args, "width", DEFAULT_WIDTH)),
        height=int(getattr(args, "height", DEFAULT_HEIGHT)),
        fps=float(getattr(args, "fps", DEFAULT_FPS)),
        trusted=bool(getattr(args, "trusted", False)),
    )
    try:
        run_tether(cfg)
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped\n")
        return 0
    except InstallError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except (HaltedError, PhoenixError, ValueError, RuntimeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    return 0
