# VeilLock — iPhone & Android

Local-first Flutter client for VeilLock. Live camera preview, modes
Private / Obfuscation / Broadcast, visual noise overlay. Offline. No
analytics.

**This overlay is the mobile obfuscation surface.** It is **not**
AES-GCM. Desktop VeilLock (Python) remains the AES-256-GCM engine.

Application id: `com.azieeliab.veillock`

## Open in Android Studio / Xcode

The `android/` and `ios/` folders here are skeleton READMEs because
this tree was written without the Flutter SDK on PATH.

```bash
cd mobile
flutter create --org com.azieeliab --project-name veillock .
# add CAMERA permission (see android/README.md and ios/README.md)
flutter pub get
flutter run
```

Then open `android/` in Android Studio, or `ios/Runner.xcworkspace` in
Xcode.

## Desktop package (counted download)

This phone app does not replace the desktop package.

# → https://veillock-download-tracker.vibelock.workers.dev/ ←

GitHub: https://github.com/AzielEliab/veillock

**Forks are welcome and always allowed.**
