# App coverage

Author: Aziel Eliab.

`veillock/coverage.py` is the source of truth. `veillock compat` prints it. This page says where the set came from and what each strategy means. It is a coverage set of widely used call and video apps. It is **not a market-share ranking**. No user counts and no share percentages are stated here.

## Sources

TalkingPointz, [The State of Videoconferencing at the End of 2025](https://talkingpointz.com/30-years-of-videoconferencing/), names Zoom, Microsoft Teams, Google Meet, and Cisco Webex as the professional core, and describes Teams as almost certainly the most widely used professional platform. That qualitative core is why those four are in the set. Share figures published elsewhere are not copied.

The rest of the set is the other desktop, browser, and phone clients people actually open for a call: Slack huddles, GoTo, RingCentral, Amazon Chime, Zoho Meeting, Dialpad, 8x8, Vonage, Cisco Jabber, Pexip, Jitsi Meet, Whereby, Nextcloud Talk, BigBlueButton, Adobe Connect, ClickMeeting, Livestorm, Lifesize, Rainbow, FaceTime, WhatsApp, Signal, Discord, Telegram, Messenger, Instagram, Snapchat, Viber, LINE, WeChat, KakaoTalk, Element, Wire, VSee, plus the creator and browser shells OBS, Streamlabs, vMix, Ecamm Live, YouTube, StreamYard, Chrome, Edge, Firefox, and Safari.

Skype stays in the set so a leftover desktop client is classified. Microsoft retired consumer Skype in May 2025. BlueJeans stays for the same reason: Verizon retired the service, which ended in 2024 ([BlueJeans](https://en.wikipedia.org/wiki/BlueJeans_Network)). Neither note is a claim that the service is still sold.

## Extension point

Add a profile. Do not add a capture fork.

```python
from veillock.coverage import AppProfile, Variant, register_profile

register_profile(AppProfile(
    app_id="example",
    title="Example Call",
    group="workplace",  # workplace, consumer, or creator
    note="One sentence of honest limits.",
    variants=(Variant(...),),
))
```

`detect(process, platform, bundle_id, url)` chooses the variant. `opens_v4l2=True` selects `engulf-v4l2` only for a native Linux app that is otherwise `pick-cam`. `sandboxed=True` (Flatpak, Snap, portal) stays `pick-cam`. `have_vcam=False` turns `win11-vcam` into `unregistered`.

## Strategy matrix

| Strategy | Camera / mic / E2E | What is true |
|----------|--------------------|--------------|
| `engulf-v4l2` | Camera | Linux, and only when that process opens `/dev/video*` itself. `bwrap` or `LD_PRELOAD`. PipeWire, the portal, Flatpak, and Snap are not engulfed. The app still gets the veil or the scramble, which is **not AES-256-GCM**. |
| `win11-vcam` | Camera | Windows 11 build 22000+ while `veilcam-register.exe` is running. `MFCreateVirtualCamera`. Friendly name argument **VeilLock**. The picker shows **VeilLock Windows Virtual Camera**. No kernel driver. VeilLock does not hook. Other cameras remain. A saved device id may still need one pick. DirectShow-only apps that skip the Windows camera pipeline will not see it. |
| `unregistered` | Camera | The Windows helper is not running. No VeilLock camera was registered. |
| `extension-getusermedia` | Camera and mic | Chromium extension wraps `getUserMedia`. Default image is a generated veil. Firefox and Safari are not this strategy. |
| `pick-cam` | Camera | The person selects VeilLock. This is the macOS path. SIP and the hardened runtime block injection. Apple-signed FaceTime cannot be injected into. |
| `impossible` | Camera and mic | The client cannot select a third-party camera. iPhone FaceTime cannot. iOS apps cannot be wrapped. |
| `linux-veillock-mic` | Mic | VeilLock creates **VeilLock Microphone** with `pactl`. Not a kernel driver. |
| `blackhole` | Mic | The app selects **BlackHole 2ch** only if BlackHole is installed. No CoreAudio plugin is shipped. |
| `vb-cable` | Mic | The app selects **CABLE Output** only if VB-Audio Virtual Cable is installed. VeilLock writes to **CABLE Input**. VeilLock does not create that microphone. |
| `insertable-streams` | E2E | Chromium only, both browsers, same key. Encoded frames are **AES-256-GCM**. A forwarding relay sees ciphertext. A server that decodes or transcodes does not recover the picture. |
| `veillock-link` | E2E | Native **AES-256-GCM** on TCP beside the call. The call app still carries the veil or the scramble. |
| `none` | E2E | No VeilLock end-to-end path on that client. |

Phone variants are `impossible` for the camera. Browser variants are `extension-getusermedia` on Chromium and `pick-cam` on Firefox and Safari. Desktop Windows variants are `win11-vcam` only while the registrar is running, and `unregistered` otherwise.

## Windows status

The source is `windows/vcam/`. Build it with MSVC on Windows (`build.ps1`). Running the registrar is what registers the camera. This repository's development environment is not Windows, so no camera is registered by importing the Python package or by running the tests. The media source never opens a physical camera. A missing `VLFC` frame is a solid veil.

API reference: [MFCreateVirtualCamera](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/nf-mfvirtualcamera-mfcreatevirtualcamera). Microsoft's virtual-camera sample documents build 22000 as the minimum. That sample is not copied into this tree.
