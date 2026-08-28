# Contributing to VeilLock

**Forks are first-class.** This project is Apache-2.0; you do not need
permission to fork, patch, or redistribute. Pull requests are welcome
if you want a change upstream. Keep a fork forever if you do not.

**Forks are welcome and always allowed.**

## How to run tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
```

Python 3.10+, numpy, cryptography, pytest. No hardware. Fixtures in
`tests/conftest.py` are synthetic RGB frames (16×16 and 64×64).

## Ground rules

1. Treat `origin` as one peer among many. Downstream forks are part of
   the download-tracking model (see `workers/download-tracker`): they
   report as `{owner}/{repo}`, not as anonymous noise.
2. **Do not invent evaluation numbers or fake latency measurements.**
   The whitepaper states a *target* of &lt;1 ms/frame for small frames.
   If you measure something, publish the machine, the frame size, and
   the method in the same breath as the number.
3. **Do not implement malware, screen scrapers, or exploits.** VeilLock
   is the encryption engine: frames the caller already holds, sealed
   before display. Capture of another process’s screen is out of scope.
4. **Keep the dependency list small.** numpy + cryptography in the core
   CLI. Optional dev extra is pytest.
5. **Forward secrecy is not optional.** Rotation must drop old session
   keys. Do not cache epoch keys “for convenience.”
6. **Do not gut crypto to make a test pass.** If a threshold is too
   tight (for example decoy entropy), loosen the test.

## Where to change things

- Session / encrypt / decrypt: `veillock/engine.py`
- KDF, AES-GCM, wrap, ratchet: `veillock/crypto.py`
- PulseCheck / HaltedError: `veillock/pulse.py`
- Phoenix Loop: `veillock/phoenix.py`
- Metadata scrub: `veillock/metadata.py`
- Modes and decoy frames: `veillock/modes.py`
- New behavior needs a synthetic test that fails without the change.

## Reporting downloads from a fork

Point users at GitHub Releases. If you cut your own releases, POST
`/event` on the download-tracker worker so counts stay attributed to
your `owner/repo` (see `workers/download-tracker/README.md`).

## License of contributions

By submitting a change you agree it is licensed under Apache-2.0, the
same license as the rest of the tree. Keep the copyright lines honest.
