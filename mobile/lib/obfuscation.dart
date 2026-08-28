import 'dart:math';
import 'package:flutter/material.dart';

/// Visual obfuscation surface for the mobile client.
///
/// Desktop VeilLock (Python) is AES-256-GCM per frame. This Dart overlay is
/// **not** AES-GCM. It ports the *idea* of the obfuscation mode: fake-window
/// noise so a capture is neither plaintext nor ciphertext snow, plus a lock
/// glyph. Documented as the mobile obfuscation surface only.
enum VeilMode { private, obfuscation, broadcast }

class FakeWindow {
  FakeWindow(this.rect, this.fill, this.bar);
  final Rect rect;
  final Color fill;
  final Color bar;
}

List<FakeWindow> buildFakeWindows(Size size, int seed) {
  final rng = Random(seed);
  final n = 2 + rng.nextInt(4);
  final out = <FakeWindow>[];
  for (var i = 0; i < n; i++) {
    final x1 = rng.nextDouble() * size.width * 0.7;
    final y1 = rng.nextDouble() * size.height * 0.7;
    final w = 80 + rng.nextDouble() * (size.width * 0.4);
    final h = 60 + rng.nextDouble() * (size.height * 0.35);
    final fill = Color.fromARGB(
      210,
      80 + rng.nextInt(130),
      80 + rng.nextInt(130),
      80 + rng.nextInt(130),
    );
    final bar = Color.fromARGB(
      230,
      40 + rng.nextInt(80),
      40 + rng.nextInt(80),
      40 + rng.nextInt(80),
    );
    out.add(FakeWindow(Rect.fromLTWH(x1, y1, w, h), fill, bar));
  }
  return out;
}

class ObfuscationPainter extends CustomPainter {
  ObfuscationPainter({
    required this.mode,
    required this.seed,
    required this.tick,
  });

  final VeilMode mode;
  final int seed;
  final int tick;

  @override
  void paint(Canvas canvas, Size size) {
    if (mode == VeilMode.private) {
      canvas.drawRect(
        Offset.zero & size,
        Paint()..color = const Color(0xCC0B0B0B),
      );
      _lock(canvas, size, const Color(0xFFC9A227));
      return;
    }
    if (mode == VeilMode.broadcast) {
      canvas.drawRect(
        Offset.zero & size,
        Paint()..color = const Color(0x660B0B0B),
      );
      _lock(canvas, size, const Color(0xFFC9A227));
      return;
    }
    // Obfuscation: synthetic UI noise (fake windows), not GCM snow.
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = const Color(0xE0101018),
    );
    final windows = buildFakeWindows(size, seed + tick ~/ 8);
    for (final w in windows) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(w.rect, const Radius.circular(4)),
        Paint()..color = w.fill,
      );
      final barH = (w.rect.height / 16).clamp(8.0, 24.0);
      canvas.drawRect(
        Rect.fromLTWH(w.rect.left, w.rect.top, w.rect.width, barH),
        Paint()..color = w.bar,
      );
    }
    _lock(canvas, size, const Color(0xFFC9A227));
  }

  void _lock(Canvas canvas, Size size, Color color) {
    final c = Offset(size.width / 2, size.height / 2);
    final p = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: c + const Offset(0, 12), width: 56, height: 40),
        const Radius.circular(6),
      ),
      p,
    );
    canvas.drawArc(
      Rect.fromCenter(center: c + const Offset(0, -8), width: 32, height: 32),
      3.14159,
      3.14159,
      false,
      p,
    );
  }

  @override
  bool shouldRepaint(covariant ObfuscationPainter old) =>
      old.mode != mode || old.seed != seed || old.tick != tick;
}
