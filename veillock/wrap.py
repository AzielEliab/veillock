"""Wrap any app that can choose a camera: veil, scramble, or explicit plaintext.

``run_wrap`` sends the public feed to a virtual camera (or a stand-in the
tests inject). The call app then encodes whatever it was given. VeilLock
does not inject into that app.

Default consent is the natural veil. After you accept the call, the
default protected feed is the keyed scramble, not the camera. Plaintext
leaves only when you set the feed to plaintext and lift the veil.
PulseCheck failure sends veil and noise.

Author: Aziel Eliab.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Iterator, TextIO

import numpy as np

from veillock.audio import AUDIO_BLOCK, comfort_noise, scramble_pcm, unveil_pcm
from veillock.azos import AzosHook
from veillock.engine import EncryptedFrame, EncryptedStream
from veillock.frames import FrameSource
from veillock.honesty import CALL_AUDIO, CALL_VIDEO, CONSENT, LOCAL_RECORDING, PLATFORM, PULSE
from veillock.modes import Mode
from veillock.pulse import AlwaysPass, HaltedError, PhoenixError, PulseCheck
from veillock.record import save_recording
from veillock.scramble import UnveilResult, public_epoch, unveil_frame
from veillock.sources import DEFAULT_HEIGHT, DEFAULT_WIDTH, resize_rgb
from veillock.tether import (
    DEVICE_NAME,
    compose_call_frame,
    halt_noise,
    open_virtual_camera,
)

DEFAULT_FPS = 15.0
MIC_NAME = "VeilLock"


@dataclass
class WrapConfig:
    """One protected call. The session key is the scramble key and the recording key."""

    source: str = "camera"
    feed: str = "scramble"
    audio_feed: str = "veil"
    mode: str = "private"
    device: int | str = 0
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: float = DEFAULT_FPS
    sample_rate: int = 16000
    obfuscation_off: bool = False
    azos_accept: bool = False
    actor: str = ""
    session_key: bytes | None = None
    receiver_secret: bytes | None = None
    pulse: PulseCheck | None = None
    rotation_interval: int = 120
    max_frames: int | None = None
    record_path: str | None = None
    rng: np.random.Generator | None = None
    azos: AzosHook = field(default_factory=AzosHook)

    def apply_consent(self) -> AzosHook:
        hook = self.azos
        if self.obfuscation_off:
            hook.set_obfuscation(False)
        if self.azos_accept:
            hook.accept_call(actor=self.actor or "user")
        return hook


@dataclass
class WrapReport:
    frames_sent: int
    labels: list[str]
    audio_labels: list[str]
    recorded: bool
    session_key: bytes


class ArrayCamera:
    """Stand-in virtual camera. Tests use this. No pyvirtualcam."""

    def __init__(self) -> None:
        self.sent: list[np.ndarray] = []

    def send(self, frame: np.ndarray) -> None:
        self.sent.append(np.ascontiguousarray(frame, dtype=np.uint8).copy())

    def sleep_until_next_frame(self) -> None:
        return None


class ArrayMic:
    """Stand-in virtual microphone. Holds the PCM the call app would encode."""

    def __init__(self) -> None:
        self.sent: list[np.ndarray] = []

    def send(self, samples: np.ndarray) -> None:
        self.sent.append(np.ascontiguousarray(samples, dtype=np.int16).ravel().copy())


def _public_audio(
    chunk: np.ndarray,
    *,
    label: str,
    audio_feed: str,
    key: bytes,
    epoch: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, str]:
    feed = str(audio_feed or "off").strip().lower()
    if feed in ("off", "none"):
        return np.zeros((0,), dtype=np.int16), "off"
    if label in ("veil", "pulse-halt") or feed == "veil":
        return comfort_noise(int(chunk.shape[0]), rng), "veil"
    if feed == "scramble":
        return scramble_pcm(chunk, key, epoch=epoch), "scramble"
    raise ValueError("audio_feed must be off, veil, or scramble")


def run_wrap(
    config: WrapConfig | None = None,
    *,
    frame_source: Iterator[np.ndarray] | None = None,
    virtual_cam: Any = None,
    pcm_source: Iterator[np.ndarray] | None = None,
    pcm_sink: Any = None,
    stop_event: threading.Event | None = None,
    log: TextIO | None = None,
) -> WrapReport:
    """Send the public feed. Optionally write an AES-256-GCM recording of the real frames."""
    cfg = config if config is not None else WrapConfig()
    if int(cfg.width) % 8 or int(cfg.height) % 8:
        raise ValueError("wrap width and height must be multiples of 8")
    feed = str(cfg.feed).strip().lower()
    if feed not in ("veil", "scramble", "plaintext"):
        raise ValueError("feed must be veil, scramble, or plaintext")
    mode = Mode.parse(cfg.mode)
    pulse: PulseCheck = cfg.pulse if cfg.pulse is not None else AlwaysPass()
    rng = cfg.rng if cfg.rng is not None else np.random.default_rng()
    out = log if log is not None else sys.stdout
    hook = cfg.apply_consent()
    import secrets as _secrets

    root = bytes(cfg.session_key) if cfg.session_key is not None else _secrets.token_bytes(32)
    if len(root) != 32:
        raise ValueError("session_key must be 32 bytes")
    receiver_secret = cfg.receiver_secret
    if mode is Mode.BROADCAST and receiver_secret is None:
        receiver_secret = _secrets.token_bytes(32)

    from veillock.engine import VeilLockSession

    session = VeilLockSession(
        session_key=root,
        rotation_interval=int(cfg.rotation_interval),
        mode=mode,
        pulse=pulse,
        receiver_secret=receiver_secret,
        rng=rng,
    )
    owns_source = frame_source is None
    source: Any = frame_source
    if source is None:
        from veillock.sources import open_source

        source = open_source(
            cfg.source,
            device=cfg.device,
            width=int(cfg.width),
            height=int(cfg.height),
            pulse=pulse,
        )
    owns_cam = virtual_cam is None
    cam = virtual_cam
    sealed: list[EncryptedFrame] = []
    pcm_real: list[np.ndarray] = []
    labels: list[str] = []
    audio_labels: list[str] = []
    sent = 0
    try:
        if cam is None:
            cam = open_virtual_camera(
                width=int(cfg.width),
                height=int(cfg.height),
                fps=float(cfg.fps),
                name=DEVICE_NAME,
            )
            enter = getattr(cam, "__enter__", None)
            if enter is not None:
                cam = enter()
        out.write(
            f"VeilLock wrap  device={DEVICE_NAME}  "
            f"{int(cfg.width)}x{int(cfg.height)}@{float(cfg.fps):g}fps  "
            f"feed={feed}  audio={cfg.audio_feed}  "
            f"veil={'on' if hook.veil_on() else 'lifted'}  reason={hook.reason()}\n"
        )
        out.write(CALL_VIDEO + "\n")
        out.write(CALL_AUDIO + "\n")
        out.write(LOCAL_RECORDING + "\n")
        out.write(PULSE + "\n")
        out.write(CONSENT + "\n")
        out.write(PLATFORM + "\n")
        out.write(f"session_key={root.hex()}\n")
        if receiver_secret is not None:
            out.write(f"receiver_secret={receiver_secret.hex()}\n")
            from veillock.callkeys import wrap_call_key

            out.write(f"wrapped_key={wrap_call_key(root, receiver_secret).hex()}\n")
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
                public = halt_noise(int(cfg.width), int(cfg.height), rng)
                label = "pulse-halt"
                produced = None
            else:
                frame = resize_rgb(frame, int(cfg.width), int(cfg.height))
                epoch = public_epoch(int(cfg.width), sent // int(cfg.rotation_interval))
                produced = compose_call_frame(
                    session,
                    frame,
                    trusted=False,
                    rng=rng,
                    hook=hook,
                    source=cfg.source,
                    tick=sent,
                    feed=feed,
                    scramble_key=root,
                    epoch=epoch,
                )
                public = produced.pixels
                label = produced.label
            send = getattr(cam, "send", None)
            if send is None:
                raise RuntimeError("virtual camera has no send()")
            send(np.ascontiguousarray(public, dtype=np.uint8))
            sleeper = getattr(cam, "sleep_until_next_frame", None)
            if sleeper is not None:
                sleeper()
            labels.append(label)

            if str(cfg.audio_feed).strip().lower() not in ("off", "none"):
                if pcm_source is None:
                    mic = np.zeros((AUDIO_BLOCK,), dtype=np.int16)
                else:
                    try:
                        mic = np.ascontiguousarray(next(pcm_source), dtype=np.int16).ravel()
                    except StopIteration:
                        mic = np.zeros((AUDIO_BLOCK,), dtype=np.int16)
                epoch = public_epoch(int(cfg.width), sent // int(cfg.rotation_interval))
                public_pcm, audio_label = _public_audio(
                    mic,
                    label=label,
                    audio_feed=str(cfg.audio_feed),
                    key=root,
                    epoch=epoch,
                    rng=rng,
                )
                audio_labels.append(audio_label)
                if pcm_sink is not None:
                    pcm_send = getattr(pcm_sink, "send", None)
                    if pcm_send is None:
                        raise RuntimeError("pcm sink has no send()")
                    pcm_send(public_pcm)
                if produced is not None and produced.sealed is not None and cfg.record_path:
                    pcm_real.append(mic)

            if produced is not None and produced.sealed is not None and cfg.record_path:
                sealed.append(produced.sealed)
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

    recorded = False
    if cfg.record_path and sealed:
        stream = EncryptedStream(
            frames=sealed,
            mode=mode.value,
            rotation_interval=int(cfg.rotation_interval),
            wrapped_key=session.wrapped_key,
            decoy=None,
        )
        pcm = np.concatenate(pcm_real) if pcm_real else None
        save_recording(
            cfg.record_path,
            stream,
            session_key=root,
            pcm=pcm,
            sample_rate=int(cfg.sample_rate),
            rotation_interval=int(cfg.rotation_interval),
        )
        recorded = True
        out.write(f"record={cfg.record_path} crypto=AES-256-GCM frames={len(sealed)}\n")
    return WrapReport(
        frames_sent=sent,
        labels=labels,
        audio_labels=audio_labels,
        recorded=recorded,
        session_key=root,
    )


def receive_stack(frames: np.ndarray, key: bytes) -> tuple[np.ndarray, list[UnveilResult]]:
    """Unveil a stack the peer captured from the call window."""
    stack = frames
    if stack.ndim == 3:
        stack = stack[None, ...]
    if stack.ndim != 4 or stack.shape[-1] != 3:
        raise ValueError("frames must be (H, W, 3) or (N, H, W, 3)")
    results = [unveil_frame(stack[i], key) for i in range(stack.shape[0])]
    images = np.stack([r.image for r in results], axis=0)
    return images, results


def receive_audio(samples: np.ndarray, key: bytes, epoch: int = 0) -> np.ndarray:
    """Undo a call-path audio scramble. This is not AES-GCM decrypt."""
    return unveil_pcm(samples, key, epoch=epoch)


def frames_from_array(frames: np.ndarray) -> FrameSource:
    arr = np.ascontiguousarray(frames, dtype=np.uint8)
    if arr.ndim == 3:
        arr = arr[None, ...]
    return FrameSource(arr)


def run_from_args(args: Any) -> int:
    """CLI entry for ``veillock wrap``."""
    import secrets as _secrets

    key = None
    raw_key = getattr(args, "key", None)
    if raw_key:
        key = bytes.fromhex(str(raw_key).strip())
    private = getattr(args, "x25519_private", None)
    peer = getattr(args, "peer_public", None)
    if private and peer:
        from veillock.callkeys import agree_x25519

        key = agree_x25519(bytes.fromhex(str(private).strip()), bytes.fromhex(str(peer).strip()))
    receiver = None
    raw_receiver = getattr(args, "receiver_secret", None)
    if raw_receiver:
        receiver = bytes.fromhex(str(raw_receiver).strip())
    if key is None:
        key = _secrets.token_bytes(32)

    frames_path = getattr(args, "frames", None)
    source_iter = None
    if frames_path:
        loaded = np.load(str(frames_path))
        source_iter = frames_from_array(loaded)

    audio_path = getattr(args, "audio_in", None)
    pcm_iter = None
    if audio_path:
        pcm = np.load(str(audio_path))
        block = int(getattr(args, "audio_block", AUDIO_BLOCK) or AUDIO_BLOCK)
        flat = np.ascontiguousarray(pcm, dtype=np.int16).ravel()

        def _chunks() -> Iterator[np.ndarray]:
            for off in range(0, len(flat), block):
                yield flat[off : off + block]

        pcm_iter = _chunks()

    preview = getattr(args, "preview_out", None)
    cam: Any = ArrayCamera() if preview else None
    mic: Any = ArrayMic() if getattr(args, "audio_out", None) else None
    cfg = WrapConfig(
        source=str(getattr(args, "source", "camera")),
        feed=str(getattr(args, "feed", "scramble")),
        audio_feed=str(getattr(args, "audio_feed", "veil")),
        mode=str(getattr(args, "mode", "private")),
        device=getattr(args, "device", 0),
        width=int(getattr(args, "width", DEFAULT_WIDTH)),
        height=int(getattr(args, "height", DEFAULT_HEIGHT)),
        fps=float(getattr(args, "fps", DEFAULT_FPS)),
        obfuscation_off=bool(getattr(args, "obfuscation_off", False)),
        azos_accept=bool(getattr(args, "azos_accept", False)),
        actor=str(getattr(args, "actor", "") or ""),
        session_key=key,
        receiver_secret=receiver,
        rotation_interval=int(getattr(args, "rotation_interval", 120)),
        max_frames=getattr(args, "max_frames", None),
        record_path=getattr(args, "record", None),
    )
    try:
        report = run_wrap(
            cfg,
            frame_source=source_iter,
            virtual_cam=cam,
            pcm_source=pcm_iter,
            pcm_sink=mic,
        )
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped\n")
        return 0
    except (HaltedError, PhoenixError, ValueError, RuntimeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    if preview and isinstance(cam, ArrayCamera) and cam.sent:
        np.save(str(preview), np.stack(cam.sent, axis=0))
        sys.stdout.write(f"preview={preview} frames={len(cam.sent)}\n")
    audio_out = getattr(args, "audio_out", None)
    if audio_out and isinstance(mic, ArrayMic) and mic.sent:
        np.save(str(audio_out), np.concatenate(mic.sent))
        sys.stdout.write(f"audio_out={audio_out}\n")
    sys.stdout.write(
        f"frames={report.frames_sent} recorded={report.recorded} "
        f"labels={','.join(report.labels)}\n"
    )
    return 0
