/* VeilLock user-mode Media Foundation source.
 * Author: Aziel Eliab.
 *
 * Frame Server CoCreates this in-proc CLSID. Samples come from
 * Local\VeilLockFrame. This file does not enumerate cameras and does
 * not open a webcam. It does not bind a physical camera to the source.
 */

#include "frame.h"

#include <initguid.h>
#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mferror.h>

#include <cstring>
#include <new>

extern "C" IMAGE_DOS_HEADER __ImageBase;

static const CLSID CLSID_VeilLockSource = {
    0xC2A1E7B4, 0x5D33, 0x4F10, {0x9A, 0x6E, 0x7B, 0x18, 0xD4, 0xF0, 0x2A, 0x91}};

static const wchar_t* kClsidKey =
    L"Software\\Classes\\CLSID\\{C2A1E7B4-5D33-4F10-9A6E-7B18D4F02A91}";

static void FillVeil(BYTE* dst, DWORD size) {
    for (DWORD i = 0; i + 3 < size; i += 4) {
        dst[i] = VEILLOCK_VEIL_B;
        dst[i + 1] = VEILLOCK_VEIL_G;
        dst[i + 2] = VEILLOCK_VEIL_R;
        dst[i + 3] = VEILLOCK_VEIL_A;
    }
}

static void CopyPublishedOrVeil(BYTE* dst, DWORD size) {
    FillVeil(dst, size);
    HANDLE mapping = OpenFileMappingW(FILE_MAP_READ, FALSE, VEILLOCK_MAPPING_NAME);
    if (!mapping) {
        return;
    }
    void* view = MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, VEILLOCK_FRAME_BYTES);
    if (!view) {
        CloseHandle(mapping);
        return;
    }
    const auto* header = static_cast<const VeilFrameHeader*>(view);
    const bool ok = std::memcmp(header->magic, VEILLOCK_FRAME_MAGIC, 4) == 0 &&
                    header->version == VEILLOCK_FRAME_VERSION &&
                    header->width == VEILLOCK_FRAME_WIDTH &&
                    header->height == VEILLOCK_FRAME_HEIGHT &&
                    header->stride == VEILLOCK_FRAME_WIDTH * 4u &&
                    header->size == VEILLOCK_FRAME_PIXELS &&
                    size >= VEILLOCK_FRAME_PIXELS;
    if (ok) {
        std::memcpy(dst, static_cast<const BYTE*>(view) + VEILLOCK_FRAME_HEADER, VEILLOCK_FRAME_PIXELS);
    }
    UnmapViewOfFile(view);
    CloseHandle(mapping);
}

class VeilStream;

class VeilSource : public IMFMediaSource {
public:
    VeilSource();
    virtual ~VeilSource();

    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override;
    STDMETHODIMP_(ULONG) AddRef() override;
    STDMETHODIMP_(ULONG) Release() override;

    STDMETHODIMP GetEvent(DWORD flags, IMFMediaEvent** event) override;
    STDMETHODIMP BeginGetEvent(IMFAsyncCallback* callback, IUnknown* state) override;
    STDMETHODIMP EndGetEvent(IMFAsyncResult* result, IMFMediaEvent** event) override;
    STDMETHODIMP QueueEvent(MediaEventType type, REFGUID ext, HRESULT status, const PROPVARIANT* value) override;

    STDMETHODIMP GetCharacteristics(DWORD* flags) override;
    STDMETHODIMP CreatePresentationDescriptor(IMFPresentationDescriptor** descriptor) override;
    STDMETHODIMP Start(IMFPresentationDescriptor* descriptor, const GUID* timeFormat, const PROPVARIANT* position) override;
    STDMETHODIMP Stop() override;
    STDMETHODIMP Pause() override;
    STDMETHODIMP Shutdown() override;

    HRESULT Init();

private:
    HRESULT MakeMediaType(IMFMediaType** type);
    long m_refs;
    CRITICAL_SECTION m_lock;
    IMFMediaEventQueue* m_queue;
    VeilStream* m_stream;
    IMFPresentationDescriptor* m_descriptor;
    bool m_shutdown;
    bool m_started;
};

class VeilStream : public IMFMediaStream {
public:
    explicit VeilStream(VeilSource* source);
    virtual ~VeilStream();

    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override;
    STDMETHODIMP_(ULONG) AddRef() override;
    STDMETHODIMP_(ULONG) Release() override;

    STDMETHODIMP GetEvent(DWORD flags, IMFMediaEvent** event) override;
    STDMETHODIMP BeginGetEvent(IMFAsyncCallback* callback, IUnknown* state) override;
    STDMETHODIMP EndGetEvent(IMFAsyncResult* result, IMFMediaEvent** event) override;
    STDMETHODIMP QueueEvent(MediaEventType type, REFGUID ext, HRESULT status, const PROPVARIANT* value) override;

    STDMETHODIMP GetMediaSource(IMFMediaSource** source) override;
    STDMETHODIMP GetStreamDescriptor(IMFStreamDescriptor** descriptor) override;
    STDMETHODIMP RequestSample(IUnknown* token) override;

    HRESULT Init(IMFStreamDescriptor* descriptor);
    HRESULT NotifyStarted();

private:
    long m_refs;
    CRITICAL_SECTION m_lock;
    IMFMediaEventQueue* m_queue;
    VeilSource* m_source;
    IMFStreamDescriptor* m_descriptor;
    LONGLONG m_index;
    bool m_shutdown;
};

class VeilFactory : public IClassFactory {
public:
    VeilFactory() : m_refs(1) {}
    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_IClassFactory) {
            *ppv = static_cast<IClassFactory*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&m_refs); }
    STDMETHODIMP_(ULONG) Release() override {
        ULONG n = InterlockedDecrement(&m_refs);
        if (!n) delete this;
        return n;
    }
    STDMETHODIMP CreateInstance(IUnknown* outer, REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        *ppv = nullptr;
        if (outer) return CLASS_E_NOAGGREGATION;
        VeilSource* source = new (std::nothrow) VeilSource();
        if (!source) return E_OUTOFMEMORY;
        HRESULT hr = source->Init();
        if (SUCCEEDED(hr)) hr = source->QueryInterface(riid, ppv);
        source->Release();
        return hr;
    }
    STDMETHODIMP LockServer(BOOL) override { return S_OK; }

private:
    long m_refs;
};

VeilSource::VeilSource()
    : m_refs(1), m_queue(nullptr), m_stream(nullptr), m_descriptor(nullptr), m_shutdown(false), m_started(false) {
    InitializeCriticalSection(&m_lock);
}

VeilSource::~VeilSource() {
    if (m_descriptor) m_descriptor->Release();
    if (m_stream) m_stream->Release();
    if (m_queue) m_queue->Release();
    DeleteCriticalSection(&m_lock);
}

HRESULT VeilSource::Init() {
    HRESULT hr = MFCreateEventQueue(&m_queue);
    if (FAILED(hr)) return hr;
    IMFMediaType* type = nullptr;
    hr = MakeMediaType(&type);
    if (FAILED(hr)) return hr;
    IMFStreamDescriptor* streamDesc = nullptr;
    hr = MFCreateStreamDescriptor(0, 1, &type, &streamDesc);
    type->Release();
    if (FAILED(hr)) return hr;
    m_stream = new (std::nothrow) VeilStream(this);
    if (!m_stream) {
        streamDesc->Release();
        return E_OUTOFMEMORY;
    }
    hr = m_stream->Init(streamDesc);
    if (FAILED(hr)) {
        streamDesc->Release();
        return hr;
    }
    hr = MFCreatePresentationDescriptor(1, &streamDesc, &m_descriptor);
    streamDesc->Release();
    if (FAILED(hr)) return hr;
    return m_descriptor->SelectStream(0);
}

HRESULT VeilSource::MakeMediaType(IMFMediaType** type) {
    IMFMediaType* media = nullptr;
    HRESULT hr = MFCreateMediaType(&media);
    if (FAILED(hr)) return hr;
    media->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
    media->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_RGB32);
    MFSetAttributeSize(media, MF_MT_FRAME_SIZE, VEILLOCK_FRAME_WIDTH, VEILLOCK_FRAME_HEIGHT);
    MFSetAttributeRatio(media, MF_MT_FRAME_RATE, 15, 1);
    MFSetAttributeRatio(media, MF_MT_PIXEL_ASPECT_RATIO, 1, 1);
    media->SetUINT32(MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive);
    media->SetUINT32(MF_MT_DEFAULT_STRIDE, VEILLOCK_FRAME_WIDTH * 4);
    media->SetUINT32(MF_MT_ALL_SAMPLES_INDEPENDENT, TRUE);
    *type = media;
    return S_OK;
}

STDMETHODIMP VeilSource::QueryInterface(REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    if (riid == IID_IUnknown || riid == IID_IMFMediaEventGenerator || riid == IID_IMFMediaSource) {
        *ppv = static_cast<IMFMediaSource*>(this);
        AddRef();
        return S_OK;
    }
    *ppv = nullptr;
    return E_NOINTERFACE;
}

STDMETHODIMP_(ULONG) VeilSource::AddRef() { return InterlockedIncrement(&m_refs); }

STDMETHODIMP_(ULONG) VeilSource::Release() {
    ULONG n = InterlockedDecrement(&m_refs);
    if (!n) delete this;
    return n;
}

STDMETHODIMP VeilSource::GetEvent(DWORD flags, IMFMediaEvent** event) {
    IMFMediaEventQueue* queue = nullptr;
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    queue = m_queue;
    queue->AddRef();
    LeaveCriticalSection(&m_lock);
    HRESULT hr = queue->GetEvent(flags, event);
    queue->Release();
    return hr;
}

STDMETHODIMP VeilSource::BeginGetEvent(IMFAsyncCallback* callback, IUnknown* state) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->BeginGetEvent(callback, state);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilSource::EndGetEvent(IMFAsyncResult* result, IMFMediaEvent** event) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->EndGetEvent(result, event);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilSource::QueueEvent(MediaEventType type, REFGUID ext, HRESULT status, const PROPVARIANT* value) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->QueueEventParamVar(type, ext, status, value);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilSource::GetCharacteristics(DWORD* flags) {
    if (!flags) return E_POINTER;
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    *flags = MFMEDIASOURCE_IS_LIVE;
    LeaveCriticalSection(&m_lock);
    return S_OK;
}

STDMETHODIMP VeilSource::CreatePresentationDescriptor(IMFPresentationDescriptor** descriptor) {
    if (!descriptor) return E_POINTER;
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_descriptor->Clone(descriptor);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilSource::Start(IMFPresentationDescriptor*, const GUID* timeFormat, const PROPVARIANT*) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    if (timeFormat && *timeFormat != GUID_NULL) {
        LeaveCriticalSection(&m_lock);
        return MF_E_UNSUPPORTED_TIME_FORMAT;
    }
    m_started = true;
    PROPVARIANT value;
    PropVariantInit(&value);
    value.vt = VT_UNKNOWN;
    value.punkVal = static_cast<IMFMediaStream*>(m_stream);
    m_stream->AddRef();
    HRESULT hr = m_queue->QueueEventParamVar(MENewStream, GUID_NULL, S_OK, &value);
    PropVariantClear(&value);
    if (SUCCEEDED(hr)) {
        PROPVARIANT empty;
        PropVariantInit(&empty);
        hr = m_queue->QueueEventParamVar(MESourceStarted, GUID_NULL, S_OK, &empty);
        PropVariantClear(&empty);
    }
    VeilStream* stream = m_stream;
    stream->AddRef();
    LeaveCriticalSection(&m_lock);
    if (SUCCEEDED(hr)) hr = stream->NotifyStarted();
    stream->Release();
    return hr;
}

STDMETHODIMP VeilSource::Stop() {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    m_started = false;
    HRESULT hr = m_queue->QueueEventParamVar(MESourceStopped, GUID_NULL, S_OK, nullptr);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilSource::Pause() { return MF_E_INVALID_STATE_TRANSITION; }

STDMETHODIMP VeilSource::Shutdown() {
    EnterCriticalSection(&m_lock);
    if (!m_shutdown && m_queue) m_queue->Shutdown();
    m_shutdown = true;
    LeaveCriticalSection(&m_lock);
    return S_OK;
}

VeilStream::VeilStream(VeilSource* source)
    : m_refs(1), m_queue(nullptr), m_source(source), m_descriptor(nullptr), m_index(0), m_shutdown(false) {
    source->AddRef();
    InitializeCriticalSection(&m_lock);
}

VeilStream::~VeilStream() {
    if (m_descriptor) m_descriptor->Release();
    if (m_source) m_source->Release();
    if (m_queue) m_queue->Release();
    DeleteCriticalSection(&m_lock);
}

HRESULT VeilStream::Init(IMFStreamDescriptor* descriptor) {
    m_descriptor = descriptor;
    m_descriptor->AddRef();
    return MFCreateEventQueue(&m_queue);
}

HRESULT VeilStream::NotifyStarted() {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->QueueEventParamVar(MEStreamStarted, GUID_NULL, S_OK, nullptr);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilStream::QueryInterface(REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    if (riid == IID_IUnknown || riid == IID_IMFMediaEventGenerator || riid == IID_IMFMediaStream) {
        *ppv = static_cast<IMFMediaStream*>(this);
        AddRef();
        return S_OK;
    }
    *ppv = nullptr;
    return E_NOINTERFACE;
}

STDMETHODIMP_(ULONG) VeilStream::AddRef() { return InterlockedIncrement(&m_refs); }

STDMETHODIMP_(ULONG) VeilStream::Release() {
    ULONG n = InterlockedDecrement(&m_refs);
    if (!n) delete this;
    return n;
}

STDMETHODIMP VeilStream::GetEvent(DWORD flags, IMFMediaEvent** event) {
    IMFMediaEventQueue* queue = nullptr;
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    queue = m_queue;
    queue->AddRef();
    LeaveCriticalSection(&m_lock);
    HRESULT hr = queue->GetEvent(flags, event);
    queue->Release();
    return hr;
}

STDMETHODIMP VeilStream::BeginGetEvent(IMFAsyncCallback* callback, IUnknown* state) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->BeginGetEvent(callback, state);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilStream::EndGetEvent(IMFAsyncResult* result, IMFMediaEvent** event) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->EndGetEvent(result, event);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilStream::QueueEvent(MediaEventType type, REFGUID ext, HRESULT status, const PROPVARIANT* value) {
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    HRESULT hr = m_queue->QueueEventParamVar(type, ext, status, value);
    LeaveCriticalSection(&m_lock);
    return hr;
}

STDMETHODIMP VeilStream::GetMediaSource(IMFMediaSource** source) {
    if (!source) return E_POINTER;
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    *source = m_source;
    m_source->AddRef();
    LeaveCriticalSection(&m_lock);
    return S_OK;
}

STDMETHODIMP VeilStream::GetStreamDescriptor(IMFStreamDescriptor** descriptor) {
    if (!descriptor) return E_POINTER;
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        return MF_E_SHUTDOWN;
    }
    *descriptor = m_descriptor;
    m_descriptor->AddRef();
    LeaveCriticalSection(&m_lock);
    return S_OK;
}

STDMETHODIMP VeilStream::RequestSample(IUnknown* token) {
    const DWORD size = VEILLOCK_FRAME_PIXELS;
    IMFSample* sample = nullptr;
    IMFMediaBuffer* buffer = nullptr;
    BYTE* data = nullptr;
    HRESULT hr = MFCreateSample(&sample);
    if (FAILED(hr)) return hr;
    hr = MFCreateMemoryBuffer(size, &buffer);
    if (FAILED(hr)) {
        sample->Release();
        return hr;
    }
    hr = buffer->Lock(&data, nullptr, nullptr);
    if (SUCCEEDED(hr)) {
        CopyPublishedOrVeil(data, size);
        buffer->Unlock();
        buffer->SetCurrentLength(size);
    }
    if (SUCCEEDED(hr)) hr = sample->AddBuffer(buffer);
    buffer->Release();
    if (FAILED(hr)) {
        sample->Release();
        return hr;
    }
    EnterCriticalSection(&m_lock);
    if (m_shutdown) {
        LeaveCriticalSection(&m_lock);
        sample->Release();
        return MF_E_SHUTDOWN;
    }
    const LONGLONG duration = 10000000LL / 15;
    sample->SetSampleTime(m_index * duration);
    sample->SetSampleDuration(duration);
    m_index += 1;
    if (token) sample->SetUnknown(MFSampleExtension_Token, token);
    hr = m_queue->QueueEventParamUnk(MEMediaSample, GUID_NULL, S_OK, sample);
    LeaveCriticalSection(&m_lock);
    sample->Release();
    return hr;
}

static HRESULT WriteInproc(const wchar_t* dllPath) {
    HKEY root = nullptr;
    LONG rc = RegCreateKeyExW(HKEY_CURRENT_USER, kClsidKey, 0, nullptr, 0, KEY_SET_VALUE, nullptr, &root, nullptr);
    if (rc != ERROR_SUCCESS) return HRESULT_FROM_WIN32(rc);
    const wchar_t* label = L"VeilLock Media Source";
    RegSetValueExW(root, nullptr, 0, REG_SZ, reinterpret_cast<const BYTE*>(label),
                   static_cast<DWORD>((wcslen(label) + 1) * sizeof(wchar_t)));
    RegCloseKey(root);
    wchar_t sub[256];
    wcscpy_s(sub, kClsidKey);
    wcscat_s(sub, L"\\InprocServer32");
    HKEY key = nullptr;
    rc = RegCreateKeyExW(HKEY_CURRENT_USER, sub, 0, nullptr, 0, KEY_SET_VALUE, nullptr, &key, nullptr);
    if (rc != ERROR_SUCCESS) return HRESULT_FROM_WIN32(rc);
    rc = RegSetValueExW(key, nullptr, 0, REG_SZ, reinterpret_cast<const BYTE*>(dllPath),
                        static_cast<DWORD>((wcslen(dllPath) + 1) * sizeof(wchar_t)));
    const wchar_t* model = L"Both";
    if (rc == ERROR_SUCCESS) {
        rc = RegSetValueExW(key, L"ThreadingModel", 0, REG_SZ, reinterpret_cast<const BYTE*>(model),
                            static_cast<DWORD>((wcslen(model) + 1) * sizeof(wchar_t)));
    }
    RegCloseKey(key);
    return rc == ERROR_SUCCESS ? S_OK : HRESULT_FROM_WIN32(rc);
}

BOOL APIENTRY DllMain(HMODULE, DWORD, LPVOID) { return TRUE; }

STDAPI DllCanUnloadNow() { return S_OK; }

STDAPI DllGetClassObject(REFCLSID clsid, REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    *ppv = nullptr;
    if (clsid != CLSID_VeilLockSource) return CLASS_E_CLASSNOTAVAILABLE;
    VeilFactory* factory = new (std::nothrow) VeilFactory();
    if (!factory) return E_OUTOFMEMORY;
    HRESULT hr = factory->QueryInterface(riid, ppv);
    factory->Release();
    return hr;
}

STDAPI DllRegisterServer() {
    wchar_t path[MAX_PATH];
    if (!GetModuleFileNameW(reinterpret_cast<HMODULE>(&__ImageBase), path, MAX_PATH)) {
        return HRESULT_FROM_WIN32(GetLastError());
    }
    return WriteInproc(path);
}

STDAPI DllUnregisterServer() {
    RegDeleteTreeW(HKEY_CURRENT_USER, kClsidKey);
    return S_OK;
}
