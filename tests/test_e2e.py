"""Encoded-frame AES-256-GCM. A relay sees ciphertext. A wrong key fails closed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from veillock.callkeys import agree_e2e, agree_x25519, generate_x25519
from veillock.crypto import DecryptError
from veillock.e2e import (
    KIND_AUDIO,
    KIND_VIDEO,
    EncodedChannel,
    decode_pcm,
    decode_picture,
    encode_pcm,
    encode_picture,
    exchange_over_relay,
    open_encoded,
    seal_encoded,
    tcp_relay,
)
from veillock.pulse import HaltedError

ROOT = Path(__file__).resolve().parents[1]
NODE = "/exec-daemon/node"
ROUNDTRIP = ROOT / "tests" / "e2e_roundtrip.mjs"


class FailPulse:
    def pci(self) -> str:
        return "FAIL"


def _node(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([NODE, str(ROUNDTRIP), *args], check=False, capture_output=True, text=True)


def test_encoded_roundtrip_rotation_and_wrong_key() -> None:
    root = bytes(range(32))
    channel = EncodedChannel(root, rotation_interval=60)
    payloads = [f"nal-{i}".encode() for i in range(61)]
    blobs = [channel.seal(payload, KIND_VIDEO) for payload in payloads]
    assert blobs[0][6:10] != blobs[60][6:10]
    for payload, blob in zip(payloads, blobs):
        opened, kind = open_encoded(blob, root)
        assert kind == KIND_VIDEO
        assert opened == payload
        assert payload not in blob
    with pytest.raises(DecryptError):
        open_encoded(blobs[0], bytes([7] * 32))
    with pytest.raises(HaltedError):
        open_encoded(blobs[0], root, pulse=FailPulse())


def test_relay_sees_ciphertext_and_consent_gates_the_camera() -> None:
    root = bytes(range(32))
    camera = b"camera-encoded-frame-secret"
    veil = b"veil-encoded-frame"
    opened, relay = exchange_over_relay([camera], root, veil=veil, lifted=False)
    assert opened == [veil]
    assert relay.saw_plaintext(camera) is False
    assert relay.saw_plaintext(veil) is False
    lifted, lifted_relay = exchange_over_relay([camera], root, veil=veil, lifted=True)
    assert lifted == [camera]
    assert lifted_relay.saw_plaintext(camera) is False
    quiet, quiet_relay = exchange_over_relay([camera], root, veil=veil, lifted=True, pulse_ok=False)
    assert quiet == []
    assert quiet_relay.forwarded == []
    with pytest.raises(DecryptError):
        exchange_over_relay([camera], root, veil=veil, lifted=True, peer_key=bytes([3] * 32))


def test_picture_and_audio_survive_the_tcp_relay() -> None:
    root = bytes(range(32))
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    frame[2:10, 3:12] = (20, 180, 40)
    pcm = np.arange(320, dtype=np.int16)
    channel = EncodedChannel(root, rotation_interval=60)
    blobs = [
        channel.seal(encode_picture(frame), KIND_VIDEO),
        channel.seal(encode_pcm(pcm), KIND_AUDIO),
    ]
    forwarded = tcp_relay(blobs)
    assert forwarded == blobs
    assert frame.tobytes() not in b"".join(forwarded)
    picture, kind_v = open_encoded(forwarded[0], root)
    audio, kind_a = open_encoded(forwarded[1], root)
    assert kind_v == KIND_VIDEO and kind_a == KIND_AUDIO
    np.testing.assert_array_equal(decode_picture(picture), frame)
    np.testing.assert_array_equal(decode_pcm(audio), pcm)


def test_x25519_e2e_label_is_not_the_scramble_key() -> None:
    priv_a, pub_a = generate_x25519()
    priv_b, pub_b = generate_x25519()
    scramble_a = agree_x25519(priv_a, pub_b)
    scramble_b = agree_x25519(priv_b, pub_a)
    e2e_a = agree_e2e(priv_a, pub_b)
    e2e_b = agree_e2e(priv_b, pub_a)
    assert scramble_a == scramble_b
    assert e2e_a == e2e_b
    assert e2e_a != scramble_a
    blob = seal_encoded(b"encoded", e2e_a, index=0, epoch=0, kind=KIND_VIDEO)
    assert open_encoded(blob, e2e_b)[0] == b"encoded"


def test_browser_crypto_matches_python_and_refuses_a_wrong_key() -> None:
    root = bytes(range(32))
    payload = b"vp8-encoded-payload"
    blob = seal_encoded(payload, root, index=4, epoch=2, kind=KIND_VIDEO)
    opened = _node("open", blob.hex(), root.hex())
    assert opened.returncode == 0
    assert bytes.fromhex(opened.stdout) == payload
    sealed = _node("seal", payload.hex(), root.hex(), "4", "2", "1")
    assert sealed.returncode == 0
    assert bytes.fromhex(sealed.stdout) == blob
    denied = _node("open", blob.hex(), bytes([9] * 32).hex())
    assert denied.returncode == 1
    assert "AES-GCM" in denied.stderr


def test_extension_picks_veillock_only_after_the_veil_is_lifted(tmp_path: Path) -> None:
    devices = [
        {"kind": "videoinput", "label": "Built-in Camera", "deviceId": "cam"},
        {"kind": "videoinput", "label": "VeilLock", "deviceId": "veilcam"},
        {"kind": "audioinput", "label": "Built-in Mic", "deviceId": "mic"},
        {"kind": "audioinput", "label": "VeilLock Microphone", "deviceId": "veilmic"},
    ]
    path = tmp_path / "devices.json"
    path.write_text(json.dumps(devices), encoding="utf-8")
    closed = json.loads(_node("pick", str(path), "0").stdout)
    assert closed["video"]["mode"] == "veil"
    assert closed["audio"]["mode"] == "veil"
    lifted = json.loads(_node("pick", str(path), "1").stdout)
    assert lifted["video"] == {"mode": "device", "deviceId": "veilcam"}
    assert lifted["audio"] == {"mode": "device", "deviceId": "veilmic"}
    streams = json.loads(_node("streams").stdout)
    assert streams["attached"] is True
    assert streams["length"] == 5 and streams["last"] == 9
    missing = json.loads(_node("no-streams").stdout)
    assert missing["attached"] is False
