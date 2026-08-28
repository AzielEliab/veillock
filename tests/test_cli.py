"""CLI: encrypt / decrypt / version."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from veillock.cli import main
from veillock import __version__


def test_version(capsys) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == f"veillock {__version__}"


def test_encrypt_decrypt_private(tmp_path: Path, frames_16: np.ndarray, session_key: bytes) -> None:
    inp = tmp_path / "frames.npy"
    outp = tmp_path / "cipher.npz"
    rec = tmp_path / "out.npy"
    np.save(inp, frames_16)
    rc = main(
        [
            "encrypt",
            "--in",
            str(inp),
            "--out",
            str(outp),
            "--mode",
            "private",
            "--key",
            session_key.hex(),
            "--rotation-interval",
            "60",
        ]
    )
    assert rc == 0
    rc = main(
        [
            "decrypt",
            "--in",
            str(outp),
            "--out",
            str(rec),
            "--key",
            session_key.hex(),
        ]
    )
    assert rc == 0
    got = np.load(rec)
    np.testing.assert_array_equal(got, frames_16)


def test_encrypt_decrypt_broadcast(tmp_path: Path, frames_16: np.ndarray, session_key: bytes) -> None:
    inp = tmp_path / "frames.npy"
    outp = tmp_path / "cipher.npz"
    rec = tmp_path / "out.npy"
    secret = b"0" * 32
    np.save(inp, frames_16)
    assert (
        main(
            [
                "encrypt",
                "--in",
                str(inp),
                "--out",
                str(outp),
                "--mode",
                "broadcast",
                "--key",
                session_key.hex(),
                "--receiver-secret",
                secret.hex(),
                "--rotation-interval",
                "60",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "decrypt",
                "--in",
                str(outp),
                "--out",
                str(rec),
                "--receiver-secret",
                secret.hex(),
            ]
        )
        == 0
    )
    np.testing.assert_array_equal(np.load(rec), frames_16)


def test_wrong_key_cli_fails(tmp_path: Path, frames_16: np.ndarray, session_key: bytes) -> None:
    inp = tmp_path / "frames.npy"
    outp = tmp_path / "cipher.npz"
    rec = tmp_path / "out.npy"
    np.save(inp, frames_16)
    main(
        [
            "encrypt",
            "--in",
            str(inp),
            "--out",
            str(outp),
            "--mode",
            "private",
            "--key",
            session_key.hex(),
            "--rotation-interval",
            "60",
        ]
    )
    bad = bytes((b ^ 1) for b in session_key)
    rc = main(["decrypt", "--in", str(outp), "--out", str(rec), "--key", bad.hex()])
    assert rc != 0
    assert not rec.exists()


def test_help_lists_ui_and_version() -> None:
    from veillock.cli import _build_parser

    text = _build_parser().format_help()
    assert "ui" in text
    assert "version" in text
    assert "tether" in text
    assert "apps" in text
    assert "encrypt" in text
    assert "decrypt" in text
    assert "127.0.0.1:8761" in text or "veillock ui" in text


def test_ui_refuses_non_loopback() -> None:
    import pytest
    from veillock.ui import LOOPBACK, make_server

    assert "127.0.0.1" in LOOPBACK
    with pytest.raises(ValueError, match="loopback"):
        make_server(host="0.0.0.0", port=0)
