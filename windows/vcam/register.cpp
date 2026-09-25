/* Register a VeilLock user-mode virtual camera, then optionally launch an app.
 * Author: Aziel Eliab.
 *
 * MFCreateVirtualCamera + Start makes the camera enumerable. Stop and Remove
 * run on the way out. This process does not hook the app and does not open
 * a physical camera. The microphone is not created here.
 */

#include "frame.h"

#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfvirtualcamera.h>

#include <cstdio>
#include <string>
#include <vector>

static bool WindowsBuildAtLeast22000(DWORD* buildOut) {
    using RtlGetVersionFn = LONG(WINAPI*)(PRTL_OSVERSIONINFOW);
    auto fn = reinterpret_cast<RtlGetVersionFn>(GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlGetVersion"));
    OSVERSIONINFOEXW info{};
    info.dwOSVersionInfoSize = sizeof(info);
    if (!fn || fn(reinterpret_cast<PRTL_OSVERSIONINFOW>(&info)) != 0) {
        return false;
    }
    if (buildOut) *buildOut = info.dwBuildNumber;
    return info.dwBuildNumber >= 22000;
}

static bool DllBesideExe(std::wstring* path) {
    wchar_t exe[MAX_PATH];
    DWORD n = GetModuleFileNameW(nullptr, exe, MAX_PATH);
    if (!n || n >= MAX_PATH) return false;
    std::wstring full(exe, n);
    size_t slash = full.find_last_of(L"\\/");
    if (slash == std::wstring::npos) return false;
    *path = full.substr(0, slash + 1) + L"veilcam.dll";
    return GetFileAttributesW(path->c_str()) != INVALID_FILE_ATTRIBUTES;
}

static HRESULT RegisterDll(const std::wstring& dllPath) {
    HMODULE dll = LoadLibraryW(dllPath.c_str());
    if (!dll) return HRESULT_FROM_WIN32(GetLastError());
    using RegFn = HRESULT(STDAPICALLTYPE*)();
    auto reg = reinterpret_cast<RegFn>(GetProcAddress(dll, "DllRegisterServer"));
    HRESULT hr = reg ? reg() : HRESULT_FROM_WIN32(ERROR_PROC_NOT_FOUND);
    FreeLibrary(dll);
    return hr;
}

static std::wstring Quote(const std::wstring& arg) {
    std::wstring out = L"\"";
    for (wchar_t ch : arg) {
        if (ch == L'"') out += L"\\\"";
        else out += ch;
    }
    out += L"\"";
    return out;
}

static HANDLE g_stop = nullptr;

static BOOL WINAPI OnCtrl(DWORD) {
    if (g_stop) SetEvent(g_stop);
    return TRUE;
}

static int LaunchAndWait(int argc, wchar_t** argv, int appIndex) {
    std::wstring cmd;
    for (int i = appIndex; i < argc; ++i) {
        if (!cmd.empty()) cmd += L" ";
        cmd += Quote(argv[i]);
    }
    std::vector<wchar_t> mutableCmd(cmd.begin(), cmd.end());
    mutableCmd.push_back(L'\0');
    STARTUPINFOW si{};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    if (!CreateProcessW(nullptr, mutableCmd.data(), nullptr, nullptr, FALSE, 0, nullptr, nullptr, &si, &pi)) {
        fwprintf(stderr, L"VeilLock could not start the app (%lu). The camera will be removed. VeilLock does not hook capture APIs.\n",
                 GetLastError());
        return 2;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return static_cast<int>(code);
}

int wmain(int argc, wchar_t** argv) {
    DWORD build = 0;
    if (!WindowsBuildAtLeast22000(&build)) {
        fwprintf(stderr,
                 L"VeilLock virtual camera needs Windows 11 build 22000 or newer. This build is %lu. "
                 L"No camera was registered. VeilLock does not hook capture APIs and does not ship a kernel driver. "
                 L"The microphone is CABLE Output only if VB-Audio Virtual Cable is installed.\n",
                 build);
        return 2;
    }
    std::wstring dll;
    if (!DllBesideExe(&dll)) {
        fwprintf(stderr, L"veilcam.dll is not beside this program. No camera was registered.\n");
        return 2;
    }
    int appIndex = -1;
    for (int i = 1; i < argc; ++i) {
        if (wcscmp(argv[i], L"--") == 0) {
            appIndex = i + 1;
            break;
        }
    }
    HRESULT hr = RegisterDll(dll);
    if (FAILED(hr)) {
        fwprintf(stderr, L"COM registration of the VeilLock media source failed (0x%08lX). No camera was registered.\n", hr);
        return 2;
    }
    hr = MFStartup(MF_VERSION);
    if (FAILED(hr)) {
        fwprintf(stderr, L"MFStartup failed (0x%08lX). No camera was registered.\n", hr);
        return 2;
    }
    IMFVirtualCamera* camera = nullptr;
    hr = MFCreateVirtualCamera(
        MFVirtualCameraType_SoftwareCameraSource,
        MFVirtualCameraLifetime_Session,
        MFVirtualCameraAccess_CurrentUser,
        VEILLOCK_FRIENDLY_NAME,
        VEILLOCK_CLSID_STRING,
        nullptr,
        0,
        &camera);
    if (FAILED(hr) || !camera) {
        fwprintf(stderr, L"MFCreateVirtualCamera failed (0x%08lX). No camera was registered. VeilLock does not hook capture APIs.\n", hr);
        MFShutdown();
        return 2;
    }
    hr = camera->Start(nullptr);
    if (FAILED(hr)) {
        fwprintf(stderr, L"IMFVirtualCamera::Start failed (0x%08lX). No camera was registered.\n", hr);
        camera->Remove();
        camera->Release();
        MFShutdown();
        return 2;
    }
    wprintf(
        L"VeilLock registered a user-mode Media Foundation camera. "
        L"The friendly name argument is VeilLock. Windows appends Windows Virtual Camera, "
        L"so the picker shows VeilLock Windows Virtual Camera. "
        L"No kernel driver. VeilLock does not hook capture APIs. "
        L"Other physical cameras remain visible. "
        L"An app that saved another device id may still need one pick. "
        L"The microphone is CABLE Output if VB-Audio Virtual Cable is installed; VeilLock does not create that microphone. "
        L"If nothing is writing Local\\VeilLockFrame, the picture is a solid veil, never the physical camera. "
        L"The call app's stream is obfuscation, not AES-256-GCM.\n");
    int code = 0;
    if (appIndex > 0 && appIndex < argc) {
        code = LaunchAndWait(argc, argv, appIndex);
    } else {
        wprintf(L"Press Ctrl+C to remove the camera.\n");
        g_stop = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        SetConsoleCtrlHandler(OnCtrl, TRUE);
        if (g_stop) WaitForSingleObject(g_stop, INFINITE);
        SetConsoleCtrlHandler(OnCtrl, FALSE);
        if (g_stop) CloseHandle(g_stop);
        g_stop = nullptr;
    }
    camera->Stop();
    camera->Remove();
    camera->Release();
    MFShutdown();
    wprintf(L"VeilLock removed the virtual camera.\n");
    return code;
}
