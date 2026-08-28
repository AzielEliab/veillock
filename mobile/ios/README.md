# iOS platform folder

This tree was authored without the Flutter SDK on PATH, so the Xcode
project is not generated here.

From the parent `mobile/` directory:

    flutter create --org com.azieeliab --project-name veillock .

That fills `ios/` (and `android/`) with the platform projects.

After `flutter create .`, add to `ios/Runner/Info.plist`:

    <key>NSCameraUsageDescription</key>
    <string>VeilLock uses the camera for a local live preview. Frames stay on device.</string>

Then:

    flutter pub get
    flutter run

Or open `ios/Runner.xcworkspace` in Xcode.
Offline. No analytics. Bundle id: `com.azieeliab.veillock`.
