# VeilLock — iPhone & Android

A local camera preview. The veil stays on until you change it under Advanced.

**Author:** Aziel Eliab

The phone overlay is a visual veil. AES-256-GCM runs in the Python desktop package.

Application id: `com.azieeliab.veillock`

## Start

1. Create the platform folders (this tree ships the Dart app).

   ```bash
   cd mobile
   flutter create --org com.azieeliab --project-name veillock .
   ```

2. Fetch packages: `flutter pub get`
3. Run: `flutter run`

## Open in Android Studio / Xcode

After `flutter create`, add the camera permission in `android/README.md` and `ios/README.md`. Open `android/` in Android Studio, or `ios/Runner.xcworkspace` in Xcode.

## Desktop package

The Python package is the counted desktop download: https://veillock-download-tracker.vibelock.workers.dev/

GitHub: https://github.com/AzielEliab/veillock

**Forks are welcome and always allowed.**
