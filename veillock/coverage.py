"""Adaptive app coverage. One registry, not one capture fork per product.

A profile says how an app gets a camera, a microphone, and (when it is
possible) true end-to-end media. ``detect`` picks the profile from a
process name, a bundle id, or a page host, then resolves the strategy
for the platform in front of it.

Adding an app is ``register_profile`` plus a test. The strategies stay:

- ``engulf-v4l2`` — Linux, and only when that process opens ``/dev/video*``
  itself. PipeWire, the portal, Flatpak, and Snap are not engulfed.
- ``win11-vcam`` — Windows 11 build 22000+ user-mode camera while
  ``veilcam-register.exe`` is running. Other cameras remain. VeilLock
  does not hook. The picker suffix is ``Windows Virtual Camera``.
- ``unregistered`` — that Windows camera is not running, so nothing named
  VeilLock was registered.
- ``extension-getusermedia`` — Chromium extension wraps ``getUserMedia``.
- ``pick-cam`` / ``pick-mic`` — the person selects the device. macOS is
  always this for the camera. Firefox and Safari are this too.
- ``impossible`` — the platform will not accept a third-party camera.
  iPhone FaceTime is this case.
- ``linux-veillock-mic``, ``blackhole``, ``vb-cable`` — the microphone.
  ``vb-cable`` means the person selects CABLE Output. VeilLock does not
  create that device.
- ``insertable-streams`` — Chromium encoded-frame AES-256-GCM. Both
  browsers need the extension and the key.
- ``veillock-link`` — native AES-256-GCM on a TCP channel beside the call.
  The call app still gets the veil or the scramble, which is not AES-256-GCM.
- ``none`` — no VeilLock end-to-end path on that client.

The built-in list is a coverage set of widely used call and video apps.
It is not a market-share ranking and it does not carry user counts.

Author: Aziel Eliab.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

CAMERA_STRATEGIES = frozenset(
    {
        "engulf-v4l2",
        "win11-vcam",
        "unregistered",
        "extension-getusermedia",
        "pick-cam",
        "impossible",
    }
)
MIC_STRATEGIES = frozenset(
    {
        "linux-veillock-mic",
        "blackhole",
        "vb-cable",
        "extension-getusermedia",
        "pick-mic",
        "impossible",
    }
)
E2E_STRATEGIES = frozenset({"insertable-streams", "veillock-link", "none"})

STRATEGY_LIMITS = {
    "engulf-v4l2": (
        "Linux engulf starts the process with bwrap or LD_PRELOAD so an open of /dev/video* "
        "receives VeilLock. PipeWire, the portal, Flatpak, and Snap are not engulfed. "
        "The app's stream is obfuscation, not AES-256-GCM."
    ),
    "win11-vcam": (
        "Windows 11 registers a user-mode camera. The friendly name argument is VeilLock; "
        "Windows appends Windows Virtual Camera. Other physical cameras remain visible, and "
        "an app that saved a device id may still need one pick. VeilLock does not hook capture APIs. "
        "No kernel driver. The app's stream is obfuscation, not AES-256-GCM."
    ),
    "unregistered": (
        "The Windows 11 registrar is not running, so no VeilLock camera was registered. "
        "VeilLock does not hook capture APIs. The app keeps whatever camera it already selected."
    ),
    "extension-getusermedia": (
        "The Chromium extension wraps getUserMedia. The default page image is a generated veil, "
        "not the real camera. Firefox and Safari are not covered by that extension."
    ),
    "pick-cam": (
        "The person selects VeilLock in the app. macOS cannot be engulfed: SIP and the hardened "
        "runtime block injection, and Apple-signed FaceTime cannot be injected into. "
        "The app's stream is obfuscation, not AES-256-GCM."
    ),
    "impossible": (
        "This client cannot select a third-party camera. iPhone FaceTime cannot. "
        "Apps cannot be wrapped on iOS."
    ),
    "linux-veillock-mic": "Linux creates VeilLock Microphone with pactl. It is not a kernel driver.",
    "blackhole": "macOS does not ship a CoreAudio plugin. The app selects BlackHole 2ch only if BlackHole is installed.",
    "vb-cable": (
        "Windows does not ship an audio driver. The app selects CABLE Output only if VB-Audio "
        "Virtual Cable is installed. VeilLock writes to CABLE Input and does not create that microphone."
    ),
    "pick-mic": "The site or app microphone picker is used. VeilLock does not create a device for this client.",
    "insertable-streams": (
        "Both Chromium browsers need the extension and the same key. Encoded frames are AES-256-GCM. "
        "A relay that forwards them unchanged sees ciphertext. A server that decodes or transcodes "
        "does not recover the picture."
    ),
    "veillock-link": (
        "veillock link is AES-256-GCM between two VeilLock users on a separate TCP channel. "
        "The call app still carries the veil or the scramble, which is not AES-256-GCM."
    ),
    "none": "No VeilLock end-to-end path on this client. The scramble is not available here either when the camera itself is impossible.",
}

_BROWSER_PROCESSES = {
    "chrome": "chromium",
    "google-chrome": "chromium",
    "chromium": "chromium",
    "brave": "chromium",
    "msedge": "chromium",
    "microsoft-edge": "chromium",
    "firefox": "firefox",
    "safari": "safari",
}


def _pairs(*items: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return items


def _cam(
    linux: str = "pick-cam",
    windows: str = "win11-vcam",
    darwin: str = "pick-cam",
    ios: str = "impossible",
    android: str = "impossible",
) -> tuple[tuple[str, str], ...]:
    return _pairs(
        ("linux", linux),
        ("windows", windows),
        ("darwin", darwin),
        ("ios", ios),
        ("android", android),
    )


def _mic_desktop() -> tuple[tuple[str, str], ...]:
    return _pairs(
        ("linux", "linux-veillock-mic"),
        ("windows", "vb-cable"),
        ("darwin", "blackhole"),
        ("ios", "impossible"),
        ("android", "impossible"),
    )


def _cam_browser() -> tuple[tuple[str, str], ...]:
    return _pairs(
        ("chromium", "extension-getusermedia"),
        ("firefox", "pick-cam"),
        ("safari", "pick-cam"),
        ("ios", "impossible"),
        ("android", "impossible"),
    )


def _mic_browser() -> tuple[tuple[str, str], ...]:
    return _pairs(
        ("chromium", "extension-getusermedia"),
        ("firefox", "pick-mic"),
        ("safari", "pick-mic"),
        ("ios", "impossible"),
        ("android", "impossible"),
    )


def _cam_mobile() -> tuple[tuple[str, str], ...]:
    return _pairs(
        ("ios", "impossible"),
        ("android", "impossible"),
        ("linux", "impossible"),
        ("windows", "impossible"),
        ("darwin", "impossible"),
    )


def _mic_mobile() -> tuple[tuple[str, str], ...]:
    return _pairs(("ios", "impossible"), ("android", "impossible"))


@dataclass(frozen=True)
class Variant:
    variant_id: str
    kind: str
    processes: tuple[str, ...]
    bundles: tuple[str, ...]
    hosts: tuple[str, ...]
    camera: tuple[tuple[str, str], ...]
    mic: tuple[tuple[str, str], ...]
    e2e: str


@dataclass(frozen=True)
class AppProfile:
    app_id: str
    title: str
    group: str
    note: str
    variants: tuple[Variant, ...]


@dataclass(frozen=True)
class Detection:
    app_id: str
    title: str
    variant_id: str
    kind: str
    platform: str
    camera: str
    mic: str
    e2e: str
    note: str
    limit: str

    def as_dict(self) -> dict[str, str]:
        return {
            "app_id": self.app_id,
            "title": self.title,
            "variant_id": self.variant_id,
            "kind": self.kind,
            "platform": self.platform,
            "camera": self.camera,
            "mic": self.mic,
            "e2e": self.e2e,
            "note": self.note,
            "limit": self.limit,
            "author": "Aziel Eliab",
        }


def _validate(profile: AppProfile) -> None:
    if not profile.app_id or not profile.variants:
        raise ValueError("a profile needs an id and at least one variant")
    if profile.group not in {"workplace", "consumer", "creator"}:
        raise ValueError("group must be workplace, consumer, or creator")
    for variant in profile.variants:
        if variant.kind not in {"native", "browser", "mobile"}:
            raise ValueError(f"{variant.variant_id} kind is not native, browser, or mobile")
        if variant.e2e not in E2E_STRATEGIES:
            raise ValueError(f"unknown e2e strategy {variant.e2e}")
        for _key, value in variant.camera:
            if value not in CAMERA_STRATEGIES or value == "unregistered":
                raise ValueError(f"{variant.variant_id} camera {value} is not a profile strategy")
        for _key, value in variant.mic:
            if value not in MIC_STRATEGIES:
                raise ValueError(f"{variant.variant_id} mic {value} is not a mic strategy")


def _native(
    app_id: str,
    processes: tuple[str, ...],
    bundles: tuple[str, ...] = (),
    camera: tuple[tuple[str, str], ...] | None = None,
) -> Variant:
    return Variant(
        variant_id=f"{app_id}-desktop",
        kind="native",
        processes=processes,
        bundles=bundles,
        hosts=(),
        camera=camera if camera is not None else _cam(),
        mic=_mic_desktop(),
        e2e="veillock-link",
    )


def _browser(app_id: str, hosts: tuple[str, ...], processes: tuple[str, ...] = ()) -> Variant:
    return Variant(
        variant_id=f"{app_id}-browser",
        kind="browser",
        processes=processes,
        bundles=(),
        hosts=hosts,
        camera=_cam_browser(),
        mic=_mic_browser(),
        e2e="insertable-streams",
    )


def _mobile(app_id: str, bundles: tuple[str, ...], processes: tuple[str, ...] = ()) -> Variant:
    return Variant(
        variant_id=f"{app_id}-mobile",
        kind="mobile",
        processes=processes,
        bundles=bundles,
        hosts=(),
        camera=_cam_mobile(),
        mic=_mic_mobile(),
        e2e="none",
    )


def _profile(
    app_id: str,
    title: str,
    group: str,
    note: str,
    variants: tuple[Variant, ...],
) -> AppProfile:
    profile = AppProfile(app_id=app_id, title=title, group=group, note=note, variants=variants)
    _validate(profile)
    return profile


def _builtin_profiles() -> tuple[AppProfile, ...]:
    """Coverage set. Sources and the retired-product notes live in docs/app-coverage.md."""
    rows: list[AppProfile] = []

    def add(profile: AppProfile) -> None:
        rows.append(profile)

    def workplace(
        app_id: str,
        title: str,
        processes: tuple[str, ...],
        hosts: tuple[str, ...] = (),
        bundles: tuple[str, ...] = (),
        note: str = "",
        mobile_bundles: tuple[str, ...] = (),
        camera: tuple[tuple[str, str], ...] | None = None,
    ) -> None:
        variants = [_native(app_id, processes, bundles, camera)]
        if hosts:
            variants.append(_browser(app_id, hosts))
        if mobile_bundles:
            variants.append(_mobile(app_id, mobile_bundles))
        add(_profile(app_id, title, "workplace", note, tuple(variants)))

    workplace(
        "zoom",
        "Zoom",
        ("zoom",),
        ("zoom.us", "zoom.com"),
        ("us.zoom.xos",),
        "Desktop clients on Linux usually open the camera through PipeWire, so the default is pick-cam. engulf-v4l2 applies only when this process opens /dev/video* itself.",
        ("us.zoom.videomeetings", "us.zoom.zrc"),
    )
    workplace(
        "teams",
        "Microsoft Teams",
        ("teams", "ms-teams"),
        ("teams.microsoft.com", "teams.live.com"),
        ("com.microsoft.teams",),
        "Teams desktop and the browser are different clients. The new desktop process is often ms-teams.",
        ("com.microsoft.teams",),
    )
    workplace(
        "meet",
        "Google Meet",
        ("meet",),
        ("meet.google.com",),
        note="Meet in a browser is the common client. A Chromium page uses the extension; Firefox and Safari stay pick-cam.",
        mobile_bundles=("com.google.android.apps.tachyon", "com.google.Meet"),
    )
    workplace(
        "webex",
        "Cisco Webex",
        ("webex", "ciscowebex", "cisco-webex"),
        ("webex.com",),
        ("com.cisco.webexmeetings",),
        mobile_bundles=("com.cisco.webexmeetings", "com.cisco.wx2.android"),
    )
    workplace(
        "skype",
        "Skype",
        ("skype",),
        ("web.skype.com",),
        note="Microsoft retired consumer Skype in May 2025. The profile stays so a leftover desktop client is classified.",
        mobile_bundles=("com.skype.raider", "com.skype.skype"),
    )
    workplace(
        "slack",
        "Slack huddles",
        ("slack",),
        ("app.slack.com",),
        ("com.tinyspeck.slackmacgap",),
        "Huddles use the same camera picker as a Slack call.",
        ("com.tinyspeck.slack", "com.Slack"),
    )
    workplace(
        "goto",
        "GoTo Meeting",
        ("goto", "g2m", "gotomeeting"),
        ("meet.goto.com", "gotomeeting.com"),
        mobile_bundles=("com.gotomeeting.GoToMeeting", "com.logmein.gotomeeting"),
    )
    workplace(
        "ringcentral",
        "RingCentral",
        ("ringcentral",),
        ("app.ringcentral.com", "ringcentral.com"),
        ("com.ringcentral.ringcentral",),
        mobile_bundles=("com.ringcentral.ringcentral", "com.glip.mobile"),
    )
    workplace(
        "bluejeans",
        "BlueJeans",
        ("bluejeans",),
        ("bluejeans.com",),
        note="Verizon retired BlueJeans. The service ended in 2024. The profile stays so an old client is classified, not because the service is live.",
        mobile_bundles=("com.bluejeans.bluejeans",),
    )
    workplace(
        "chime",
        "Amazon Chime",
        ("chime", "amazon-chime"),
        ("app.chime.aws",),
        mobile_bundles=("com.amazonaws.services.chime", "com.amazon.aws.Chime"),
    )
    workplace("zoho", "Zoho Meeting", ("zoho", "zohomeeting"), ("meeting.zoho.com",), mobile_bundles=("com.zoho.meeting",))
    workplace("dialpad", "Dialpad", ("dialpad",), ("dialpad.com",), mobile_bundles=("co.dialpad.ios", "co.dialpad.android"))
    workplace(
        "eightbyeight",
        "8x8",
        ("8x8", "eightbyeight", "vod"),
        ("8x8.vc",),
        mobile_bundles=("com.eght.meetings",),
    )
    workplace("vonage", "Vonage", ("vonage",), ("meetings.vonage.com",), mobile_bundles=("com.vonage.meeting",))
    workplace(
        "jabber",
        "Cisco Jabber",
        ("jabber", "ciscojabber"),
        note="Jabber is a desktop and mobile UC client. There is no separate VeilLock capture fork.",
        mobile_bundles=("com.cisco.jabber", "com.cisco.im"),
    )
    workplace("pexip", "Pexip", ("pexip",), ("pexip.me",), note="Pexip web and the desktop app share this profile.")
    workplace("jitsi", "Jitsi Meet", ("jitsi", "jitsi-meet"), ("meet.jit.si",), note="Jitsi in Chromium uses the extension. A native build that opens /dev/video* can be engulfed.")
    workplace("whereby", "Whereby", ("whereby",), ("whereby.com",))
    workplace("nextcloud", "Nextcloud Talk", ("nextcloud", "nextcloud-talk"), ("nextcloud.com",), note="Talk's desktop and web clients. A self-hosted host still matches when the process name is nextcloud.")
    workplace("bigbluebutton", "BigBlueButton", ("bigbluebutton",), ("bigbluebutton.org",), note="BBB is used in the browser. The HTML5 client is the browser variant.")
    workplace("adobe-connect", "Adobe Connect", ("connect", "adobeconnect"), ("adobeconnect.com",))
    workplace("clickmeeting", "ClickMeeting", ("clickmeeting",), ("clickmeeting.com",))
    workplace("livestorm", "Livestorm", ("livestorm",), ("livestorm.co",), note="Livestorm rooms run in the browser.")
    workplace("lifesize", "Lifesize", ("lifesize",), ("lifesize.com",), mobile_bundles=("com.lifesize.cloud",))
    workplace("rainbow", "Alcatel-Lucent Rainbow", ("rainbow",), ("web.openrainbow.com",), mobile_bundles=("com.alcatel.rainbow",))

    def consumer(
        app_id: str,
        title: str,
        processes: tuple[str, ...],
        hosts: tuple[str, ...] = (),
        mobile_bundles: tuple[str, ...] = (),
        note: str = "",
        camera: tuple[tuple[str, str], ...] | None = None,
        desktop: bool = True,
    ) -> None:
        variants: list[Variant] = []
        if desktop:
            variants.append(_native(app_id, processes, (), camera))
        if hosts:
            variants.append(_browser(app_id, hosts))
        if mobile_bundles:
            variants.append(_mobile(app_id, mobile_bundles, () if desktop else processes))
        add(_profile(app_id, title, "consumer", note, tuple(variants)))

    consumer(
        "facetime",
        "FaceTime",
        ("facetime",),
        mobile_bundles=("com.apple.facetime",),
        note="Mac FaceTime can select a virtual camera. iPhone FaceTime cannot select a third-party camera or microphone. Apple-signed FaceTime cannot be injected into.",
        camera=_cam(linux="impossible", windows="impossible", darwin="pick-cam"),
    )
    consumer(
        "whatsapp",
        "WhatsApp",
        ("whatsapp",),
        ("web.whatsapp.com",),
        ("com.whatsapp", "net.whatsapp.WhatsApp"),
        "WhatsApp desktop can pick a camera when the call screen offers one. The phone app cannot.",
    )
    consumer(
        "signal",
        "Signal",
        ("signal",),
        mobile_bundles=("org.thoughtcrime.securesms", "org.whispersystems.signal"),
        note="Signal desktop can pick a camera when the call screen offers one. There is no official Signal web calling client. The phone app cannot pick a third-party camera.",
    )
    consumer(
        "discord",
        "Discord",
        ("discord",),
        ("discord.com",),
        ("com.discord", "com.hammerandchisel.discord"),
    )
    consumer(
        "telegram",
        "Telegram",
        ("telegram",),
        ("web.telegram.org",),
        ("org.telegram.messenger", "ph.telegra.Telegraph"),
    )
    consumer(
        "messenger",
        "Messenger",
        ("messenger",),
        ("messenger.com",),
        ("com.facebook.orca", "com.facebook.Messenger"),
    )
    consumer(
        "instagram",
        "Instagram",
        ("instagram",),
        mobile_bundles=("com.instagram.android", "com.burbn.instagram"),
        note="Instagram calls on a phone cannot select a third-party camera. A desktop window is still pick-cam where the app offers a picker.",
    )
    consumer(
        "snapchat",
        "Snapchat",
        ("snapchat",),
        mobile_bundles=("com.snapchat.android", "com.toyopagroup.picaboo"),
        note="Snapchat on a phone cannot select a third-party camera.",
    )
    consumer("viber", "Viber", ("viber",), mobile_bundles=("com.viber", "com.viber.voip"))
    consumer("line", "LINE", ("line",), mobile_bundles=("jp.naver.line.android", "jp.naver.line"))
    consumer("wechat", "WeChat", ("wechat", "weixin"), mobile_bundles=("com.tencent.mm", "com.tencent.xin"))
    consumer("kakaotalk", "KakaoTalk", ("kakaotalk",), mobile_bundles=("com.kakao.talk",))
    consumer(
        "element",
        "Element",
        ("element",),
        ("app.element.io",),
        ("im.vector.app", "im.vector.riot"),
        "Element is a Matrix client. The web app in Chromium uses the extension.",
    )
    consumer("wire", "Wire", ("wire",), ("app.wire.com",), ("com.wire", "com.wearezeta.zclient.ios"))
    consumer("vsee", "VSee", ("vsee",), ("vsee.com",), note="VSee clinic and desktop calls. The phone app, where present, cannot take a third-party camera from VeilLock.")

    add(
        _profile(
            "obs",
            "OBS Studio",
            "creator",
            "OBS selects VeilLock as a video capture source. An OBS recording of that source is the veil or the scramble, not the AES-256-GCM .veilrec.",
            (_native("obs", ("obs", "obs64", "obs-studio")),),
        )
    )
    add(
        _profile(
            "streamlabs",
            "Streamlabs",
            "creator",
            "Streamlabs Desktop selects a capture device the same way OBS does.",
            (_native("streamlabs", ("streamlabs", "streamlabs-desktop")),),
        )
    )
    add(
        _profile(
            "vmix",
            "vMix",
            "creator",
            "vMix is a Windows compositor. It can add the registered VeilLock camera as an input. It does not get a Linux or macOS engulf path.",
            (
                _native(
                    "vmix",
                    ("vmix", "vmix64"),
                    camera=_cam(linux="impossible", windows="win11-vcam", darwin="impossible"),
                ),
            ),
        )
    )
    add(
        _profile(
            "ecamm",
            "Ecamm Live",
            "creator",
            "Ecamm Live is a macOS app. SIP blocks injection. The camera is a pick. There is no Windows or iOS third-party camera path.",
            (
                _native(
                    "ecamm",
                    ("ecamm", "ecammlive"),
                    camera=_cam(linux="impossible", windows="impossible", darwin="pick-cam"),
                ),
            ),
        )
    )
    add(
        _profile(
            "youtube",
            "YouTube",
            "creator",
            "YouTube live in the browser. Chromium can take the extension. A phone broadcast cannot select VeilLock.",
            (
                _browser("youtube", ("youtube.com", "studio.youtube.com")),
                _mobile("youtube", ("com.google.android.youtube", "com.google.ios.youtube")),
            ),
        )
    )
    add(
        _profile(
            "streamyard",
            "StreamYard",
            "creator",
            "StreamYard runs in the browser. Chromium uses the extension. Firefox and Safari stay on the site camera picker.",
            (_browser("streamyard", ("streamyard.com",)),),
        )
    )
    add(
        _profile(
            "chrome",
            "Google Chrome",
            "creator",
            "Chrome is the browser shell. A calling page is detected from its host and uses that app's profile. Chrome itself is extension-getusermedia.",
            (_browser("chrome", (), ("chrome", "google-chrome", "chromium", "brave")),),
        )
    )
    add(
        _profile(
            "edge",
            "Microsoft Edge",
            "creator",
            "Edge is Chromium. The extension can wrap getUserMedia. A calling page still matches that product's host first.",
            (_browser("edge", (), ("msedge", "microsoft-edge")),),
        )
    )
    add(
        _profile(
            "firefox",
            "Firefox",
            "creator",
            "The VeilLock extension does not run in Firefox. The page uses the site camera picker. Encoded-frame AES-256-GCM is not attached.",
            (
                Variant(
                    variant_id="firefox-browser",
                    kind="browser",
                    processes=("firefox",),
                    bundles=(),
                    hosts=(),
                    camera=_cam_browser(),
                    mic=_mic_browser(),
                    e2e="insertable-streams",
                ),
            ),
        )
    )
    add(
        _profile(
            "safari",
            "Safari",
            "creator",
            "The VeilLock extension does not run in Safari. The page uses the site camera picker. Apple-signed Safari is not injected into.",
            (
                Variant(
                    variant_id="safari-browser",
                    kind="browser",
                    processes=("safari",),
                    bundles=("com.apple.safari",),
                    hosts=(),
                    camera=_cam_browser(),
                    mic=_mic_browser(),
                    e2e="insertable-streams",
                ),
            ),
        )
    )
    if len(rows) != 50:
        raise RuntimeError(f"coverage set drifted to {len(rows)}")
    return tuple(rows)


_BUILTINS: tuple[AppProfile, ...] = _builtin_profiles()
_REGISTRY: dict[str, AppProfile] = {profile.app_id: profile for profile in _BUILTINS}


def builtin_profiles() -> tuple[AppProfile, ...]:
    return _BUILTINS


def profiles() -> tuple[AppProfile, ...]:
    return tuple(_REGISTRY[key] for key in sorted(_REGISTRY))


def register_profile(profile: AppProfile) -> None:
    """Extension point. Replaces an id already in the registry."""
    _validate(profile)
    _REGISTRY[profile.app_id] = profile


def remove_profile(app_id: str) -> None:
    _REGISTRY.pop(app_id, None)


def _basename(process: str | None) -> str:
    if not process:
        return ""
    name = process.replace("\\", "/").rstrip("/").split("/")[-1].lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _host(url: str | None) -> str:
    if not url:
        return ""
    text = url.strip()
    if "://" not in text:
        text = "https://" + text
    host = (urlparse(text).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _engine(process: str | None, platform: str | None) -> str | None:
    name = _basename(process)
    if name in _BROWSER_PROCESSES:
        return _BROWSER_PROCESSES[name]
    if platform in {"chromium", "firefox", "safari"}:
        return platform
    return None


def _resolve_camera(
    variant: Variant,
    platform: str,
    engine: str | None,
    *,
    have_vcam: bool,
    opens_v4l2: bool,
    sandboxed: bool,
) -> str:
    table = dict(variant.camera)
    if variant.kind == "browser":
        key = engine
        if key and key in table:
            return table[key]
        if platform in table:
            return table[platform]
        return "pick-cam" if platform in {"linux", "windows", "darwin"} else "impossible"
    choice = table.get(platform, "impossible")
    if choice == "win11-vcam" and not have_vcam:
        return "unregistered"
    if platform == "linux" and variant.kind == "native" and choice == "pick-cam":
        if sandboxed:
            return "pick-cam"
        if opens_v4l2:
            return "engulf-v4l2"
    return choice


def _resolve_mic(variant: Variant, platform: str, engine: str | None) -> str:
    table = dict(variant.mic)
    if variant.kind == "browser":
        key = engine
        if key and key in table:
            return table[key]
        if platform in table:
            return table[platform]
        return "pick-mic" if platform in {"linux", "windows", "darwin"} else "impossible"
    return table.get(platform, "impossible")


def _resolve_e2e(variant: Variant, platform: str, engine: str | None) -> str:
    if variant.e2e == "insertable-streams":
        if engine == "chromium" or platform == "chromium":
            return "insertable-streams"
        return "none"
    return variant.e2e


def _score(variant: Variant, name: str, host: str, bundle: str, platform: str) -> int:
    score = 0
    if host and any(host == item or host.endswith("." + item) for item in variant.hosts):
        score += 8 + max((len(item) for item in variant.hosts), default=0)
    if name and name in variant.processes:
        score += 5
    if bundle and bundle.lower() in {item.lower() for item in variant.bundles}:
        score += 5
    if score == 0:
        return 0
    if platform in {"ios", "android"} and variant.kind == "mobile":
        score += 2
    elif platform in {"chromium", "firefox", "safari"} and variant.kind == "browser":
        score += 2
    elif platform in {"linux", "windows", "darwin"} and variant.kind == "native":
        score += 1
    return score


def detect(
    process: str | None = None,
    platform: str | None = None,
    bundle_id: str | None = None,
    url: str | None = None,
    *,
    have_vcam: bool | None = None,
    opens_v4l2: bool = False,
    sandboxed: bool = False,
) -> Detection | None:
    """Pick a profile and the strategy that actually fits this process."""
    from veillock.wincam import helper_present

    plat = (platform or "").lower().strip()
    if plat.startswith("win"):
        plat = "windows"
    elif plat in {"mac", "macos", "darwin"}:
        plat = "darwin"
    elif plat.startswith("linux"):
        plat = "linux"
    name = _basename(process)
    host = _host(url)
    bundle = (bundle_id or "").strip()
    engine = _engine(process, plat)
    best: tuple[int, AppProfile, Variant] | None = None
    for profile in _REGISTRY.values():
        for variant in profile.variants:
            score = _score(variant, name, host, bundle, plat or engine or "")
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, profile, variant)
    if best is None:
        return None
    _score_value, profile, variant = best
    vcam = helper_present() if have_vcam is None else bool(have_vcam)
    camera = _resolve_camera(
        variant,
        plat,
        engine,
        have_vcam=vcam,
        opens_v4l2=opens_v4l2,
        sandboxed=sandboxed,
    )
    mic = _resolve_mic(variant, plat, engine)
    e2e = _resolve_e2e(variant, plat, engine)
    limit = " ".join(
        part
        for part in (
            STRATEGY_LIMITS.get(camera, ""),
            STRATEGY_LIMITS.get(mic, ""),
            STRATEGY_LIMITS.get(e2e, ""),
        )
        if part
    )
    return Detection(
        app_id=profile.app_id,
        title=profile.title,
        variant_id=variant.variant_id,
        kind=variant.kind,
        platform=plat,
        camera=camera,
        mic=mic,
        e2e=e2e,
        note=profile.note,
        limit=limit,
    )


def _native_camera(profile: AppProfile, platform: str) -> str:
    strategy = "no desktop client"
    for variant in profile.variants:
        if variant.kind == "native":
            strategy = dict(variant.camera).get(platform, "impossible")
            break
    if strategy == "win11-vcam":
        return "win11-vcam when the registrar is running, otherwise unregistered"
    if strategy == "pick-cam" and platform == "linux":
        return "pick-cam (engulf-v4l2 only if this process opens /dev/video* and is not sandboxed)"
    return strategy


def _line(profile: AppProfile) -> str:
    kinds = ", ".join(variant.kind for variant in profile.variants)
    phone = "impossible" if any(variant.kind == "mobile" for variant in profile.variants) else "no phone client"
    browser = "yes" if any(variant.kind == "browser" for variant in profile.variants) else "no"
    return (
        f"{profile.title} [{kinds}]. "
        f"Desktop camera linux={_native_camera(profile, 'linux')}; "
        f"windows={_native_camera(profile, 'windows')}; "
        f"darwin={_native_camera(profile, 'darwin')}. "
        f"Browser={browser}. Phone={phone}. "
        f"Mic on desktop: VeilLock Microphone, BlackHole 2ch, or CABLE Output. "
        f"{profile.note}"
    ).strip()


def coverage_guide_text() -> str:
    lines = [
        "",
        "App coverage — one profile registry",
        "------------------------------------",
        "This is a coverage set of widely used call and video apps, not a market-share ranking.",
        "No user counts are stated here. A new app is a profile passed to register_profile, plus a test.",
        "There is no per-app capture fork.",
        "Strategies: engulf-v4l2, win11-vcam, unregistered, extension-getusermedia, pick-cam, impossible.",
        "True AES-256-GCM between VeilLock peers is veillock link, or Chromium insertable streams when both browsers have the extension and the key.",
        "The call app's own picture stays a veil or a keyed scramble, which is not AES-256-GCM.",
        "Windows microphone: CABLE Output if VB-Audio Virtual Cable is installed. VeilLock does not create that microphone.",
        "iPhone FaceTime cannot select a third-party camera.",
        "Windows 11 camera: friendly name VeilLock, picker text VeilLock Windows Virtual Camera, and only while veilcam-register.exe is running. VeilLock does not hook. Other cameras remain.",
        "",
    ]
    for profile in _BUILTINS:
        lines.append(f"{profile.app_id}: {_line(profile)}")
    lines.append("")
    return "\n".join(lines)
