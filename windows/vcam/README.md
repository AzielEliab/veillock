# VeilLock Windows 11 virtual camera

Author: Aziel Eliab.

This directory is a user-mode Media Foundation camera. It is not a kernel driver and it is not a DirectShow filter. `veilcam-register.exe` calls [`MFCreateVirtualCamera`](https://learn.microsoft.com/en-us/windows/win32/api/mfvirtualcamera/nf-mfvirtualcamera-mfcreatevirtualcamera) (`MFVirtualCameraType_SoftwareCameraSource`, per-user, session lifetime). The custom media source CLSID is `{C2A1E7B4-5D33-4F10-9A6E-7B18D4F02A91}`.

Microsoft documents Windows 11 build 22000 as the minimum. The registrar reads the build and exits without registering anything on an older system. The friendly-name argument is `VeilLock`. The camera pipeline appends ` Windows Virtual Camera`, so the picker shows **VeilLock Windows Virtual Camera**.

## What this does not do

- It does not hook Zoom, Teams, Skype, Discord, or any other process.
- It does not hide physical cameras. Windows has no per-process `/dev` the way Linux `bwrap` does. An app that saved another device id can still open that camera.
- It does not call `IMFVirtualCamera::AddDeviceSourceInfo` and it does not enumerate or open a webcam. If `Local\VeilLockFrame` is missing or the `VLFC` magic is wrong, every sample is a solid veil.
- It does not create a microphone. If VB-Audio Virtual Cable is installed, the call app still selects **CABLE Output** and VeilLock writes to **CABLE Input**.
- DirectShow-only apps that never use the Windows camera pipeline will not see this device.
- The media type is RGB32, 640×480, 15 fps. An app that refuses that type will not use VeilLock. This tree does not claim otherwise.
- Building these sources on a machine does not register a camera. Registration happens only when `veilcam-register.exe` runs on Windows 11 and `Start` succeeds.

## Build

From a Visual Studio x64 developer prompt, on Windows:

```powershell
.\build.ps1
.\veilcam-register.exe -- Zoom.exe
```

The registrar stays up, launches the command after `--`, then calls `Stop` and `Remove` so the camera leaves the list. Without a command, it waits until Ctrl+C and then removes the camera.

Feed pixels from Python with `veillock.wincam` (or `veillock wrap`, which publishes the public veil or scramble, never the raw camera while the veil is on). The shared-memory layout is the 32-byte header in `frame.h`.
