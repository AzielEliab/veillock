import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import 'obfuscation.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const VeilLockApp());
}

class VeilLockApp extends StatelessWidget {
  const VeilLockApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VeilLock',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const PreviewPage(),
    );
  }
}

class PreviewPage extends StatefulWidget {
  const PreviewPage({super.key});

  @override
  State<PreviewPage> createState() => _PreviewPageState();
}

class _PreviewPageState extends State<PreviewPage> {
  CameraController? _cam;
  String? _camError;
  VeilMode _mode = VeilMode.obfuscation;
  int _tick = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 120), (_) {
      if (mounted && _mode == VeilMode.obfuscation) {
        setState(() => _tick++);
      }
    });
    _openCamera();
  }

  Future<void> _openCamera() async {
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) {
        setState(() => _camError = 'No camera on this device.');
        return;
      }
      final front = cams.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cams.first,
      );
      final ctrl = CameraController(
        front,
        ResolutionPreset.medium,
        enableAudio: false,
      );
      await ctrl.initialize();
      if (!mounted) {
        await ctrl.dispose();
        return;
      }
      setState(() {
        _cam = ctrl;
        _camError = null;
      });
    } catch (e) {
      setState(() => _camError = e.toString());
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _cam?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ready = _cam != null && _cam!.value.isInitialized;
    return Scaffold(
      appBar: AppBar(
        title: const Text('VeilLock'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const SettingsPage(),
                ),
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: SegmentedButton<VeilMode>(
              segments: const [
                ButtonSegment(value: VeilMode.private, label: Text('Private')),
                ButtonSegment(
                  value: VeilMode.obfuscation,
                  label: Text('Obfuscation'),
                ),
                ButtonSegment(
                  value: VeilMode.broadcast,
                  label: Text('Broadcast'),
                ),
              ],
              selected: {_mode},
              onSelectionChanged: (s) => setState(() => _mode = s.first),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              _caption(_mode),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (ready)
                      CameraPreview(_cam!)
                    else
                      Container(
                        color: kSurface,
                        alignment: Alignment.center,
                        child: Text(
                          _camError ?? 'Opening camera…',
                          textAlign: TextAlign.center,
                        ),
                      ),
                    CustomPaint(
                      painter: ObfuscationPainter(
                        mode: _mode,
                        seed: 7,
                        tick: _tick,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _caption(VeilMode m) {
    switch (m) {
      case VeilMode.private:
        return 'Private: preview dimmed, lock on. Session key is not exported. '
            'This overlay is not AES-GCM.';
      case VeilMode.obfuscation:
        return 'Obfuscation: synthetic UI noise over the live camera. '
            'Mobile obfuscation surface — not AES-GCM ciphertext.';
      case VeilMode.broadcast:
        return 'Broadcast: authorized-receiver idea. HMAC wrap lives on desktop. '
            'Phone shows lock + live preview only.';
    }
  }
}

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  static const _body =
      'This app is a local-first VeilLock client. Frames never leave the '
      'device. No analytics.\n\n'
      'What this phone app is\n'
      'A live camera preview with Private / Obfuscation / Broadcast modes. '
      'Obfuscation draws fake-window noise (a Dart port of desktop synthetic '
      'UI noise) plus a lock icon. v1 does not implement AES-256-GCM. Do not '
      'claim GCM on this surface. The Python desktop engine remains the '
      'AES-GCM pipeline.\n\n'
      'Desktop tether into Zoom / FaceTime\n'
      'The phone does not become a virtual webcam. On the desktop package:\n'
      '  pip install -e ".[tether]"\n'
      '  veillock tether --source camera --mode obfuscation --device 0\n'
      'That publishes a virtual camera named VeilLock. The call app chooses it:\n'
      '  Zoom (desktop): Settings → Video → Camera → VeilLock\n'
      '  FaceTime (Mac): Video menu → VeilLock\n'
      'VeilLock does not MITM the call.\n\n'
      'FaceTime / iOS limits\n'
      'iOS cannot inject a replacement camera into FaceTime. Apple does not '
      'give third-party apps a virtual-camera API on iPhone. This IPA cannot '
      'feed FaceTime or Zoom on the phone. Use the desktop tether.\n\n'
      'Not in this app\n'
      'GodLock and MirageGrid network features are not included. Offline only.';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: const SingleChildScrollView(
        padding: EdgeInsets.all(20),
        child: Text(_body, style: TextStyle(height: 1.45)),
      ),
    );
  }
}
