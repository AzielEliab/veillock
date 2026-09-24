"""Call wrap: scramble survives a synthetic codec; AES recording does not travel the call."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest

from veillock.audio import comfort_noise, scramble_pcm, unveil_pcm
from veillock.callkeys import agree_x25519, generate_x25519, unwrap_call_key, wrap_call_key
from veillock.cli import main
from veillock.codecsim import jpeg_like, phase_discard_pcm, spectral_quantize_pcm
from veillock.crypto import DecryptError
from veillock.engine import VeilLockSession
from veillock.honesty import CALL_AUDIO, CALL_VIDEO, LOCAL_RECORDING
from veillock.pulse import HaltedError
from veillock.record import play_recording, seal_recording
from veillock.scramble import BLOCK, has_scramble_magic, public_epoch, scramble_frame, unveil_frame
from veillock.tether import APPS_GUIDE
from veillock.wrap import ArrayCamera, ArrayMic, WrapConfig, run_wrap


class FailPulse:
    def pci(self) -> str:
        return "FAIL"


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    x = a.astype(np.float64).ravel()
    y = b.astype(np.float64).ravel()
    x = x - float(x.mean())
    y = y - float(y.mean())
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    if denom == 0.0:
        return 0.0
    return float(x @ y) / denom


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def _scene(h: int = 128, w: int = 128, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    face = ((xx - w * 0.5) ** 2) / (w * w * 0.08) + ((yy - h * 0.45) ** 2) / (h * h * 0.10) < 1.0
    frame[face] = (210, 160, 140)
    frame[h // 3 : h // 3 + 6, w // 3 : w // 3 + 6] = (20, 20, 30)
    frame[h // 3 : h // 3 + 6, w // 2 : w // 2 + 6] = (20, 20, 30)
    frame[h // 2 : h // 2 + 4, w // 2 - 6 : w // 2 + 6] = (170, 50, 60)
    return np.ascontiguousarray(frame, dtype=np.uint8)


def _body(frame: np.ndarray) -> np.ndarray:
    return frame[BLOCK:-BLOCK]


def _tone(n: int = 320 * 8, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros(n, dtype=np.int16)
    block = 320
    for i in range(n // block):
        t = np.linspace(0, 6 + i * 0.4, block)
        wave = np.sin(t) * (2500 + i * 300) + rng.normal(0, 40, block)
        out[i * block : (i + 1) * block] = wave.astype(np.int16)
    return out


def test_scramble_is_not_aes_and_roundtrips_without_codec() -> None:
    src = _scene()
    key = bytes(range(32))
    wrong = bytes([9] * 32)
    public = scramble_frame(src, key, epoch=2)
    assert has_scramble_magic(public)
    assert not np.array_equal(public, src)
    assert _corr(_body(public), _body(src)) < 0.25
    assert "not AES-256-GCM" in CALL_VIDEO
    good = unveil_frame(public, key)
    assert good.authorized is True
    assert good.kind == "scramble"
    assert good.epoch == 2
    np.testing.assert_array_equal(_body(good.image), _body(src))
    denied = unveil_frame(public, wrong)
    assert denied.authorized is False
    assert denied.kind == "unauthorized"
    assert not np.array_equal(_body(denied.image), _body(src))
    assert _mae(_body(denied.image), _body(src)) > 20


def test_scramble_survives_jpeg_like_only_with_the_key() -> None:
    src = _scene(96, 128, seed=11)
    key = bytes(range(32))
    wrong = bytes([3] * 32)
    public = scramble_frame(src, key, epoch=1)
    for quality in (40, 30):
        lossy = jpeg_like(public, quality=quality, chroma_420=False)
        good = unveil_frame(lossy, key)
        assert good.authorized, f"q={quality} {good.kind} {good.note}"
        assert _corr(_body(good.image), _body(src)) > 0.90
        assert _mae(_body(good.image), _body(src)) < 20
        assert not np.array_equal(_body(good.image), _body(src))
        denied = unveil_frame(lossy, wrong)
        assert denied.authorized is False
        assert _corr(_body(denied.image), _body(src)) < 0.55
    # 4:2:0 keeps the key check and a recognizable picture. Color is worse.
    chroma = jpeg_like(public, quality=40, chroma_420=True)
    chroma_peer = unveil_frame(chroma, key)
    assert chroma_peer.authorized
    assert _corr(_body(chroma_peer.image), _body(src)) > 0.70
    assert unveil_frame(chroma, wrong).authorized is False


def test_gcm_painted_as_pixels_does_not_survive_the_same_codec(session_key: bytes) -> None:
    """Why the call path cannot be AES-GCM: the codec edits the bytes."""
    src = _scene()
    sess = VeilLockSession(session_key=session_key, rotation_interval=60, mode="private")
    sealed = sess.encrypt_frame(src)
    need = src.size
    raw = (sealed.ciphertext * ((need // max(len(sealed.ciphertext), 1)) + 1))[:need]
    painted = np.frombuffer(raw, dtype=np.uint8).reshape(src.shape).copy()
    lossy = jpeg_like(painted, quality=40)
    assert not np.array_equal(lossy, painted)
    assert _mae(lossy, painted) > 5


def test_audio_scramble_limits() -> None:
    key = bytes(range(32))
    wrong = bytes([4] * 32)
    pcm = _tone()
    veiled = comfort_noise(len(pcm), np.random.default_rng(5))
    assert not np.array_equal(veiled, pcm)
    public = scramble_pcm(pcm, key, epoch=1)
    assert not np.array_equal(public, pcm)
    assert _corr(public, pcm) < 0.55
    back = unveil_pcm(public, key, epoch=1)
    np.testing.assert_array_equal(back, pcm)
    assert not np.array_equal(unveil_pcm(public, wrong, epoch=1), pcm)
    assert _corr(unveil_pcm(public, wrong, epoch=1), pcm) < 0.55

    quant = spectral_quantize_pcm(public)
    recovered = unveil_pcm(quant, key, epoch=1)
    assert _corr(recovered, pcm) > 0.85
    assert not np.array_equal(recovered, pcm)
    assert _corr(unveil_pcm(quant, wrong, epoch=1), pcm) < 0.55

    destroyed = phase_discard_pcm(public)
    phase_back = unveil_pcm(destroyed, key, epoch=1)
    assert _corr(phase_back, pcm) < 0.35
    assert "not AES-256-GCM" in CALL_AUDIO
    assert "Opus" in CALL_AUDIO


def test_x25519_and_wrapped_key_agree() -> None:
    a_priv, a_pub = generate_x25519()
    b_priv, b_pub = generate_x25519()
    left = agree_x25519(a_priv, b_pub)
    right = agree_x25519(b_priv, a_pub)
    assert left == right
    assert len(left) == 32
    secret = bytes(range(16))
    wrapped = wrap_call_key(left, secret)
    assert unwrap_call_key(wrapped, secret) == left
    with pytest.raises(DecryptError):
        unwrap_call_key(wrapped, b"other-secret")


def test_aes_recording_roundtrip_and_rotation(tmp_path: Path, session_key: bytes) -> None:
    frames = np.stack([_scene(32, 32, seed=i) for i in range(4)], axis=0)
    pcm = _tone(3200)
    path = tmp_path / "clip.veilrec"
    seal_recording(str(path), frames, session_key, pcm=pcm, rotation_interval=60)
    blob = path.read_bytes()
    assert frames.tobytes() not in blob
    played = play_recording(str(path), session_key)
    np.testing.assert_array_equal(played.frames, frames)
    assert played.pcm is not None
    np.testing.assert_array_equal(played.pcm, pcm)
    assert "AES-256-GCM" in played.note
    assert "AES-256-GCM" in LOCAL_RECORDING
    with pytest.raises(DecryptError):
        play_recording(str(path), bytes([7] * 32))

    many = np.zeros((61, 8, 8, 3), dtype=np.uint8)
    for i in range(61):
        many[i, :, :] = (i * 3) % 255
        many[i, 1:4, 1:4] = (200, i % 255, 40)
    long_path = tmp_path / "long.veilrec"
    seal_recording(str(long_path), many, session_key, rotation_interval=60)
    again = play_recording(str(long_path), session_key)
    np.testing.assert_array_equal(again.frames, many)


def test_recording_refuses_plaintext_when_pulse_fails(tmp_path: Path, session_key: bytes) -> None:
    path = tmp_path / "nope.veilrec"
    with pytest.raises(HaltedError, match="recording refused"):
        seal_recording(str(path), _scene()[None, ...], session_key, pulse=FailPulse())
    assert not path.exists()


def test_wrap_consent_scramble_record_and_pulse(tmp_path: Path) -> None:
    key = bytes(range(32))
    plain = _scene()
    cam = ArrayCamera()
    mic = ArrayMic()
    pcm = _tone(320)
    veiled = run_wrap(
        WrapConfig(
            feed="scramble",
            audio_feed="scramble",
            width=128,
            height=128,
            max_frames=1,
            session_key=key,
            rotation_interval=60,
            record_path=str(tmp_path / "while-veiled.veilrec"),
            rng=np.random.default_rng(2),
        ),
        frame_source=iter([plain]),
        virtual_cam=cam,
        pcm_source=iter([pcm]),
        pcm_sink=mic,
        log=io.StringIO(),
    )
    assert veiled.labels == ["veil"]
    assert veiled.audio_labels == ["veil"]
    assert not has_scramble_magic(cam.sent[0])
    assert not np.array_equal(cam.sent[0], plain)
    assert not np.array_equal(mic.sent[0], pcm)
    sealed = play_recording(str(tmp_path / "while-veiled.veilrec"), key)
    np.testing.assert_array_equal(sealed.frames[0], plain)
    assert sealed.pcm is not None
    np.testing.assert_array_equal(sealed.pcm, pcm)

    cam2 = ArrayCamera()
    mic2 = ArrayMic()
    lifted = run_wrap(
        WrapConfig(
            feed="scramble",
            audio_feed="scramble",
            width=128,
            height=128,
            max_frames=1,
            session_key=key,
            azos_accept=True,
            actor="Aziel Eliab",
            rotation_interval=60,
            rng=np.random.default_rng(2),
        ),
        frame_source=iter([plain.copy()]),
        virtual_cam=cam2,
        pcm_source=iter([pcm.copy()]),
        pcm_sink=mic2,
        log=io.StringIO(),
    )
    assert lifted.labels == ["scramble"]
    assert lifted.audio_labels == ["scramble"]
    assert has_scramble_magic(cam2.sent[0])
    lossy = jpeg_like(cam2.sent[0], quality=40)
    peer = unveil_frame(lossy, key)
    assert peer.authorized
    assert _corr(_body(peer.image), _body(plain)) > 0.90
    assert unveil_frame(lossy, bytes([8] * 32)).authorized is False
    np.testing.assert_array_equal(unveil_pcm(mic2.sent[0], key, epoch=public_epoch(128, 0)), pcm)

    cam3 = ArrayCamera()
    halted = run_wrap(
        WrapConfig(
            feed="scramble",
            audio_feed="scramble",
            width=128,
            height=128,
            max_frames=1,
            session_key=key,
            azos_accept=True,
            pulse=FailPulse(),
            rotation_interval=60,
            record_path=str(tmp_path / "halted.veilrec"),
            rng=np.random.default_rng(2),
        ),
        frame_source=iter([plain.copy()]),
        virtual_cam=cam3,
        pcm_source=iter([pcm.copy()]),
        pcm_sink=ArrayMic(),
        log=io.StringIO(),
    )
    assert halted.labels == ["pulse-halt"]
    assert halted.recorded is False
    assert not path_has_plaintext(tmp_path / "halted.veilrec", plain)
    assert not np.array_equal(cam3.sent[0], plain)
    assert not has_scramble_magic(cam3.sent[0])


def path_has_plaintext(path: Path, plain: np.ndarray) -> bool:
    return path.exists() and plain.tobytes() in path.read_bytes()


def test_docs_and_worker_say_what_is_encrypted() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    paper = (root / "docs" / "whitepaper.md").read_text(encoding="utf-8")
    runtime = (root / "workers" / "download-tracker" / "src" / "runtime.js").read_text(encoding="utf-8")
    for blob in (readme, skill, paper, runtime, APPS_GUIDE):
        assert "not AES-256-GCM" in blob or "not\nAES-256-GCM" in blob or "**Not AES-256-GCM.**" in blob
        assert "AES-256-GCM" in blob
        assert "iPhone FaceTime cannot" in blob or "iOS FaceTime cannot" in blob
    assert "Discord" in readme and "Discord" in runtime
    assert "aes_on_call_path: false" in runtime
    assert "increments_downloads: false" in runtime
    assert "function wrapContract" in runtime
    # The wrap description must not be the download counter.
    start = runtime.index("if (path === \"/v1/wrap\"")
    handler = runtime[start : start + 180]
    assert "increment" not in handler
    for name in ("ChatGPT", "Grok", "Venice", "Claude", "Cursor", "Glama", "Perplexity", "Copilot", "Gemini", "Mistral", "Meta AI", "Apple Intelligence", "Amazon Q", "DuckAssist", "You.com", "Cohere"):
        assert name in readme
        assert name in skill


def test_cli_apps_lists_desktop_clients_and_the_iphone_limit(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["apps"]) == 0
    out = capsys.readouterr().out
    assert out == APPS_GUIDE or out == APPS_GUIDE + "\n" or APPS_GUIDE in out
    for name in ("Zoom", "Skype", "FaceTime", "Meet", "Teams", "Discord", "WhatsApp", "Signal", "OBS", "WebRTC"):
        assert name in out
    assert "iPhone FaceTime cannot" in out
    assert "not AES-256-GCM" in out
    assert "AES-256-GCM" in out


def test_cli_keygen_agree_record_play_receive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["keygen"]) == 0
    text = capsys.readouterr().out
    assert "psk=" in text and "x25519_private=" in text and "x25519_public=" in text
    assert "not AES-256-GCM" in text
    lines = dict(line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("The "))
    psk = lines["psk"].strip()
    priv = lines["x25519_private"].strip()
    pub = lines["x25519_public"].strip()
    other_priv, other_pub = generate_x25519()
    assert main(["agree", "--private", priv, "--peer-public", other_pub.hex()]) == 0
    agreed = capsys.readouterr().out
    assert "session_key=" in agreed
    assert "not AES-256-GCM" in agreed

    frames = np.stack([_scene(128, 128, seed=1), _scene(128, 128, seed=2)], axis=0)
    npy = tmp_path / "frames.npy"
    np.save(npy, frames)
    rec = tmp_path / "clip.veilrec"
    assert main(["record", "--in", str(npy), "--out", str(rec), "--key", psk, "--rotation-interval", "60"]) == 0
    assert "AES-256-GCM" in capsys.readouterr().out
    played = tmp_path / "back.npy"
    assert main(["play", "--in", str(rec), "--export", "--out", str(played), "--key", psk]) == 0
    np.testing.assert_array_equal(np.load(played), frames)
    assert main(["play", "--in", str(rec), "--out", str(tmp_path / "bad.npy"), "--key", "11" * 32]) == 1

    preview = tmp_path / "public.npy"
    assert (
        main(
            [
                "wrap",
                "--frames",
                str(npy),
                "--feed",
                "scramble",
                "--audio-feed",
                "off",
                "--key",
                psk,
                "--azos-accept",
                "--width",
                "128",
                "--height",
                "128",
                "--preview-out",
                str(preview),
                "--rotation-interval",
                "60",
            ]
        )
        == 0
    )
    public = np.load(preview)
    assert public.shape[0] == 2
    assert has_scramble_magic(public[0])
    out = tmp_path / "unveiled.npy"
    assert main(["receive", "--in", str(preview), "--export", "--out", str(out), "--key", psk]) == 0
    unveiled = np.load(out)
    np.testing.assert_array_equal(_body(unveiled[0]), _body(frames[0]))
    denied = tmp_path / "denied.npy"
    assert main(["receive", "--in", str(preview), "--export", "--out", str(denied), "--key", "22" * 32]) == 0
    assert not np.array_equal(_body(np.load(denied)[0]), _body(frames[0]))
    _ = pub  # public half of the keygen pair; agree used the private half
    _ = other_priv
