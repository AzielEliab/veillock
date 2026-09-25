"""Recordings stay AES-256-GCM on disk. Playback is in memory. A wrong key opens nothing."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from veillock.cli import main
from veillock.crypto import DecryptError
from veillock.record import HEADER_LEN, ChunkVault, play_recording, seal_recording

ROOT = Path(__file__).resolve().parents[1]
NODE = "/exec-daemon/node"


def _frame(seed: int) -> np.ndarray:
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    img[:, :] = (seed, 40, 90)
    img[1:4, 2:6] = (200, seed, 10)
    return img


def test_audio_only_round_trip_and_wrong_key_opens_nothing(tmp_path: Path) -> None:
    pcm = np.arange(1000, dtype=np.int16)
    path = tmp_path / "audio.veilrec"
    key = bytes(range(32))
    seal_recording(str(path), np.zeros((0, 1, 1, 3), dtype=np.uint8), key, pcm=pcm, rotation_interval=60)
    played = play_recording(str(path), key)
    assert played.frames.shape[0] == 0
    np.testing.assert_array_equal(played.pcm, pcm)
    assert pcm.tobytes() not in path.read_bytes()
    with pytest.raises(DecryptError):
        play_recording(str(path), bytes([9] * 32))
    assert not (tmp_path / "audio.wav").exists()
    assert list(tmp_path.glob("*.npy")) == []


def test_no_plaintext_in_the_recording_or_a_temp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(scratch))

    def _boom(*_args, **_kwargs):
        raise AssertionError("recording tried to create a temp file")

    monkeypatch.setattr(tempfile, "mkstemp", _boom)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", _boom)
    frames = np.stack([_frame(1), _frame(2)], axis=0)
    pcm = np.array([1000, -2000, 3000, -4000], dtype=np.int16)
    path = tmp_path / "both.veilrec"
    key = bytes(range(32))
    seal_recording(str(path), frames, key, pcm=pcm, rotation_interval=60)
    raw = path.read_bytes()
    assert frames.tobytes() not in raw
    assert pcm.tobytes() not in raw
    assert key not in raw
    assert list(scratch.iterdir()) == []
    played = play_recording(str(path), key)
    np.testing.assert_array_equal(played.frames, frames)
    np.testing.assert_array_equal(played.pcm, pcm)


def test_crash_mid_record_keeps_only_sealed_chunks(tmp_path: Path) -> None:
    path = tmp_path / "torn.veilrec"
    key = bytes(range(32))
    first, second = _frame(4), _frame(5)
    vault = ChunkVault(str(path), key, rotation_interval=60)
    vault.write_video(first)
    vault.write_video(second)
    vault.close()
    torn = path.read_bytes() + b"\x00\x00\x01\x00" + b"not-a-sealed-chunk"
    path.write_bytes(torn)
    played = play_recording(str(path), key)
    np.testing.assert_array_equal(played.frames, np.stack([first, second], axis=0))
    assert first.tobytes() not in path.read_bytes()
    assert b"not-a-sealed-chunk" in path.read_bytes()


def test_play_does_not_export_plaintext_unless_asked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    frames = _frame(7)[None, ...]
    path = tmp_path / "clip.veilrec"
    key = bytes(range(32)).hex()
    npy = tmp_path / "in.npy"
    np.save(npy, frames)
    assert main(["record", "--in", str(npy), "--out", str(path), "--key", key, "--rotation-interval", "60"]) == 0
    exported = tmp_path / "out.npy"
    assert main(["play", "--in", str(path), "--out", str(exported), "--key", key]) == 2
    assert not exported.exists()
    assert "leaves VeilLock" in capsys.readouterr().err
    assert main(["play", "--in", str(path), "--key", key]) == 0
    assert "in_memory=1" in capsys.readouterr().out
    assert list(tmp_path.glob("*.npy")) == [npy]


def test_extension_chunk_matches_python_and_rejects_a_wrong_key(tmp_path: Path) -> None:
    key = bytes(range(32))
    frame = _frame(3)
    path = tmp_path / "one.veilrec"
    vault = ChunkVault(str(path), key, rotation_interval=60)
    vault.write_video(frame)
    vault.close()
    raw = path.read_bytes()
    size = int.from_bytes(raw[HEADER_LEN : HEADER_LEN + 4], "big")
    body = raw[HEADER_LEN + 4 : HEADER_LEN + 4 + size]
    proc = subprocess.run(
        [
            NODE,
            str(ROOT / "tests" / "vault_roundtrip.mjs"),
            "seal",
            frame.tobytes().hex(),
            key.hex(),
            "0",
            "0",
            "1",
            "8",
            "8",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert bytes.fromhex(proc.stdout) == body
    opened = subprocess.run(
        [NODE, str(ROOT / "tests" / "vault_roundtrip.mjs"), "open", body.hex(), key.hex(), "0", "0", "1", "8", "8"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert opened.returncode == 0
    assert bytes.fromhex(opened.stdout) == frame.tobytes()
    denied = subprocess.run(
        [NODE, str(ROOT / "tests" / "vault_roundtrip.mjs"), "open", body.hex(), bytes([4] * 32).hex(), "0", "0", "1", "8", "8"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert denied.returncode == 1
