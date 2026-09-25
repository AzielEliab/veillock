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
      theme: buildAppTheme(Brightness.light),
      darkTheme: buildAppTheme(Brightness.dark),
      themeMode: ThemeMode.system,
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
        setState(() => _camError = 'No camera on this device. On a computer, run veillock ui.');
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
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Text(
              'Keeps this camera veiled until you lift it.',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                _caption(_mode),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
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
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: ExpansionTile(
              title: const Text('Advanced'),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
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
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _caption(VeilMode m) {
    switch (m) {
      case VeilMode.private:
        return 'Veil on. Private keeps the preview dimmed, with the lock showing.';
      case VeilMode.obfuscation:
        return 'Veil on. People see a natural camera veil until you lift it.';
      case VeilMode.broadcast:
        return 'Veil on. Broadcast keeps the lock on this preview.';
    }
  }
}

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  static const _body =
      'This app is a local-first VeilLock preview. Frames stay on this '
      'device.\n\n'
      'The camera stays under a privacy veil until you turn obfuscation '
      'off or accept a call through AZ-OS. You control both paths.\n\n'
      'About\n'
      'Private, Obfuscation, and Broadcast live under Advanced. The overlay '
      'is a visual veil plus a lock icon. AES-256-GCM runs in the Python '
      'desktop engine, together with the AZ-OS hook.\n\n'
      'Desktop tether into Zoom / FaceTime\n'
      'The virtual camera named VeilLock comes from the desktop package:\n'
      '  pip install -e ".[tether]"\n'
      '  veillock tether --source camera --mode obfuscation --device 0\n'
      'The call app chooses it:\n'
      '  Zoom (desktop): Settings → Video → Camera → VeilLock\n'
      '  FaceTime (Mac): Video menu → VeilLock\n'
      'The public feed stays veiled until you lift it.\n\n'
      'iPhone FaceTime\n'
      'iPhone FaceTime has no third-party camera picker. Use the desktop '
      'tether for FaceTime on a Mac, Zoom, Skype, Meet, or Teams.';

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
