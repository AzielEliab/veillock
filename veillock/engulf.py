"""Launch a call app so its own camera open receives VeilLock, where that is possible.

What actually works
-------------------
Linux, and only for a program that opens ``/dev/video*`` itself:
``bwrap`` builds a fresh ``/dev`` and bind-mounts the VeilLock device on
``/dev/video0``. Without ``bwrap``, ``LD_PRELOAD`` of
``engulf/libveilcapture.c`` redirects ``open()`` of ``/dev/video*`` to
that device. The preload does not hide the real nodes from a directory
listing, and it does not wrap PipeWire, PulseAudio, or ``/dev/snd``.

Linux PipeWire and xdg-desktop-portal apps are not engulfed. The camera
daemon is a different process.

Windows is not engulfed. No signed DirectShow or Media Foundation source
is shipped, and VeilLock does not hook capture APIs inside another process.

macOS is not engulfed. SIP and the hardened runtime block library
injection. Apple-signed FaceTime cannot be injected into. Fall back to
the virtual camera, which the user still has to select.

Chromium WebRTC is engulfed by ``extension/``, not by this launcher.
The extension wraps ``getUserMedia``. iOS apps cannot be wrapped.

``veillock engulf`` starts the command you name. It does not attach to a
process that is already running.

Author: Aziel Eliab.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRELOAD_SOURCE = REPO_ROOT / "engulf" / "libveilcapture.c"
PRELOAD_LIBRARY = REPO_ROOT / "engulf" / "libveilcapture.so"

BROWSER_NAMES = ("chrome", "chromium", "firefox", "msedge", "safari", "brave", "google-chrome")


@dataclass(frozen=True)
class EngulfRow:
    platform: str
    app_type: str
    method: str
    encryption: str
    engulfs: bool


ENGULF_ROWS: tuple[EngulfRow, ...] = (
    EngulfRow(
        platform="Linux",
        app_type="Native app that opens /dev/video* itself (not PipeWire)",
        method=(
            "veillock engulf -- <app> starts that app. With bwrap, a fresh /dev "
            "is created and the VeilLock device is the only /dev/video0; /dev/snd "
            "is absent. Without bwrap, LD_PRELOAD redirects open() of /dev/video* "
            "to the VeilLock device and does not hide the other nodes. "
            "PULSE_SOURCE=VeilLock is set for Pulse clients. PipeWire is not wrapped."
        ),
        encryption=(
            "The app receives the veil or the scramble. That is obfuscation, not "
            "AES-256-GCM. AES-256-GCM between two VeilLock users is veillock link, "
            "or the browser extension's encoded frames. Both ends need VeilLock."
        ),
        engulfs=True,
    ),
    EngulfRow(
        platform="Linux",
        app_type="PipeWire, xdg-desktop-portal, Flatpak, or Snap camera",
        method=(
            "Not engulfed. The portal or PipeWire daemon is outside the sandbox "
            "and still opens the real camera. Use the virtual camera, or the "
            "browser extension for a WebRTC page."
        ),
        encryption=(
            "The app's stream stays the veil or the scramble (obfuscation, not "
            "AES-256-GCM) unless both users join veillock link."
        ),
        engulfs=False,
    ),
    EngulfRow(
        platform="Windows",
        app_type="Zoom, Skype, Teams, Discord, and other native call apps",
        method=(
            "Not engulfed. No signed DirectShow or Media Foundation source is "
            "shipped. VeilLock does not hook capture APIs in the app. The app "
            "still uses whatever camera it has selected."
        ),
        encryption=(
            "The app's stream is obfuscation, not AES-256-GCM. Two VeilLock users "
            "can still run veillock link beside the call. That link is AES-256-GCM. "
            "The call provider sees the veil, not the link."
        ),
        engulfs=False,
    ),
    EngulfRow(
        platform="macOS",
        app_type="FaceTime, and hardened or Apple-signed apps such as Zoom and Teams",
        method=(
            "Not engulfed. SIP and the hardened runtime block DYLD_INSERT_LIBRARIES. "
            "Apple-signed FaceTime cannot be injected into. Fall back to the virtual "
            "camera, which you still select in the app. BlackHole is the microphone "
            "only if you installed it."
        ),
        encryption=(
            "The app's stream is obfuscation, not AES-256-GCM. veillock link beside "
            "the call is AES-256-GCM between two VeilLock users."
        ),
        engulfs=False,
    ),
    EngulfRow(
        platform="Browser (Chromium)",
        app_type="Meet, Teams web, Zoom web, Discord web, and any WebRTC page",
        method=(
            "Install extension/. It runs at document_start in the page and wraps "
            "getUserMedia. By default the page gets a generated veil and noise, not "
            "the real camera or microphone. After you lift the veil, the page gets "
            "a device whose label contains VeilLock (or BlackHole / CABLE Output for "
            "audio) and never the bare hardware device. This launcher does not "
            "LD_PRELOAD the browser."
        ),
        encryption=(
            "When both browsers have the extension and the same key, each encoded "
            "frame is AES-256-GCM before it is packetized. A relay that forwards "
            "those frames unchanged sees ciphertext. A server that decodes or "
            "transcodes does not recover the picture. Without the key, frames are "
            "not encrypted and the page only has the veil. The extension does not "
            "run PulseCheck. Peers without the extension cannot decrypt. The keyed "
            "scramble remains the obfuscation fallback for them."
        ),
        engulfs=True,
    ),
    EngulfRow(
        platform="iOS",
        app_type="Any app, including iPhone FaceTime",
        method="Apps cannot be wrapped. There is no engulf on iOS. iPhone FaceTime cannot select a third-party camera or microphone either.",
        encryption="No VeilLock encryption path on iOS. The phone app sends its own camera.",
        engulfs=False,
    ),
    EngulfRow(
        platform="VeilLock to VeilLock",
        app_type="Any native call, beside the app",
        method=(
            "veillock link carries deflate-encoded frames and audio over TCP "
            "between the two users. The call app still sends only the veil or "
            "the scramble. The decrypted picture is shown by VeilLock, not inside "
            "Zoom or FaceTime. This is not the call provider's connection."
        ),
        encryption=(
            "AES-256-GCM on each encoded blob, with key rotation. The key is the "
            "X25519 HKDF label veillock-e2e-media-v1, or a 32-byte pre-shared key. "
            "Both ends need VeilLock. A wrong key fails closed. PulseCheck failure "
            "sends nothing. Until you lift the veil, the sealed payload is the veil, "
            "not the camera. An observer on this TCP channel sees ciphertext. "
            "An observer on the call sees the veil. The scramble is obfuscation "
            "for peers who do not run VeilLock."
        ),
        engulfs=False,
    ),
)


def engulf_guide_text() -> str:
    lines = [
        "",
        "Engulf — the app uses VeilLock without a camera picker",
        "-------------------------------------------------------",
        "veillock engulf starts the app you name. It does not attach to a",
        "process that is already running. iPhone FaceTime cannot be wrapped.",
        "",
    ]
    for row in ENGULF_ROWS:
        lines.append(f"{row.platform} — {row.app_type}")
        lines.append(f"  Engulf: {'yes' if row.engulfs else 'no'}")
        lines.append(f"  How: {row.method}")
        lines.append(f"  Encryption: {row.encryption}")
        lines.append("")
    lines.append(
        "The keyed scramble (veillock wrap --feed scramble) is obfuscation, "
        "not AES-256-GCM. It is the fallback when the other person has no VeilLock."
    )
    lines.append("")
    return "\n".join(lines)


def _is_browser(argv: list[str]) -> bool:
    if not argv:
        return False
    name = Path(argv[0]).name.lower()
    return any(token in name for token in BROWSER_NAMES)


@dataclass
class EngulfPlan:
    platform: str
    engulfs: bool
    argv: list[str]
    env: dict[str, str]
    note: str

    def as_dict(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "engulfs": self.engulfs,
            "argv": list(self.argv),
            "note": self.note,
            "author": "Aziel Eliab",
        }


def host_platform(name: str | None = None) -> str:
    raw = (name if name is not None else sys.platform).lower()
    if raw.startswith("linux"):
        return "linux"
    if raw == "darwin":
        return "darwin"
    if raw.startswith("win"):
        return "windows"
    if raw in ("ios", "iphone"):
        return "ios"
    return raw


def bwrap_command(app: list[str], video_device: str) -> list[str]:
    """Fresh /dev plus the VeilLock node at /dev/video0.

    Display and runtime sockets are bound so a desktop app can start.
    Binding the runtime dir also lets the app talk to PipeWire, which is
    outside this sandbox and is not engulfed.
    """
    cmd = [
        "bwrap",
        "--die-with-parent",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind-try",
        "/lib",
        "/lib",
        "--ro-bind-try",
        "/lib64",
        "/lib64",
        "--ro-bind-try",
        "/bin",
        "/bin",
        "--ro-bind-try",
        "/etc",
        "/etc",
        "--bind-try",
        "/home",
        "/home",
        "--bind-try",
        "/tmp",
        "/tmp",
        "--bind",
        video_device,
        "/dev/video0",
    ]
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        cmd.extend(["--bind-try", runtime, runtime])
    x11 = "/tmp/.X11-unix"
    if os.path.isdir(x11):
        cmd.extend(["--bind-try", x11, x11])
    cmd.append("--")
    cmd.extend(app)
    return cmd


def plan_engulf(
    app: list[str],
    *,
    platform: str | None = None,
    have_bwrap: bool | None = None,
    preload: str | None = None,
    video_device: str = "/dev/video10",
) -> EngulfPlan:
    plat = host_platform(platform)
    env = dict(os.environ)
    env["VEILLOCK_VIDEO"] = video_device
    env["PULSE_SOURCE"] = "VeilLock"
    if plat == "ios":
        return EngulfPlan(
            plat,
            False,
            [],
            env,
            "iOS apps cannot be wrapped. iPhone FaceTime cannot select a third-party camera or microphone.",
        )
    if plat == "darwin":
        return EngulfPlan(
            plat,
            False,
            [],
            env,
            "macOS engulf is refused. SIP and the hardened runtime block injection. "
            "Apple-signed FaceTime cannot be injected into. Select the virtual camera in the app. "
            "The app's stream is obfuscation, not AES-256-GCM.",
        )
    if plat == "windows":
        return EngulfPlan(
            plat,
            False,
            [],
            env,
            "Windows engulf is refused. No DirectShow or Media Foundation source is shipped, "
            "and VeilLock does not hook the app's capture APIs. The app's stream is obfuscation, not AES-256-GCM.",
        )
    if plat != "linux":
        return EngulfPlan(plat, False, [], env, f"No engulf on {plat}.")
    if _is_browser(app):
        return EngulfPlan(
            plat,
            False,
            [],
            env,
            "This launcher does not wrap a browser process. Install extension/ so getUserMedia returns VeilLock. "
            "Encoded-frame AES-256-GCM needs the extension on both browsers and the same key.",
        )
    bwrap = shutil.which("bwrap") is not None if have_bwrap is None else bool(have_bwrap)
    library = preload if preload is not None else (str(PRELOAD_LIBRARY) if PRELOAD_LIBRARY.is_file() else "")
    if bwrap:
        return EngulfPlan(
            plat,
            True,
            bwrap_command(app, video_device),
            env,
            "bwrap hides other video nodes and /dev/snd. /dev/video0 is the VeilLock device. "
            "PipeWire clients are not engulfed, because the daemon is outside this sandbox. "
            "The app receives the veil or the scramble, which is not AES-256-GCM.",
        )
    if library:
        env["LD_PRELOAD"] = library if not env.get("LD_PRELOAD") else library + ":" + env["LD_PRELOAD"]
        return EngulfPlan(
            plat,
            True,
            list(app),
            env,
            "LD_PRELOAD redirects open() of /dev/video* to the VeilLock device. "
            "It does not hide those nodes from a directory listing, and it does not wrap "
            "PipeWire, PulseAudio, or /dev/snd. The app's stream is obfuscation, not AES-256-GCM.",
        )
    return EngulfPlan(
        plat,
        False,
        [],
        env,
        "Linux engulf needs bwrap, or a built engulf/libveilcapture.so "
        "(gcc -shared -fPIC -o engulf/libveilcapture.so engulf/libveilcapture.c -ldl). "
        "Neither is available, so the app was not started and the real camera was not wrapped.",
    )


def run_engulf(app: list[str], *, video_device: str = "/dev/video10") -> int:
    plan = plan_engulf(app, video_device=video_device)
    sys.stdout.write(plan.note + "\n")
    sys.stdout.write(engulf_guide_text())
    if not plan.engulfs or not plan.argv:
        return 2
    argv = plan.argv
    sys.stdout.flush()
    os.execvpe(argv[0], argv, plan.env)
    return 2
