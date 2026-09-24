/* VeilLock shared-memory frame. Author: Aziel Eliab.
 * The media source reads this mapping. It never opens a physical camera.
 * Python (veillock/wincam.py) writes the same 32-byte header.
 */
#pragma once

#include <stdint.h>

#define VEILLOCK_FRAME_MAGIC "VLFC"
#define VEILLOCK_FRAME_VERSION 1u
#define VEILLOCK_FRAME_WIDTH 640u
#define VEILLOCK_FRAME_HEIGHT 480u
#define VEILLOCK_FRAME_HEADER 32u
#define VEILLOCK_FRAME_PIXELS (VEILLOCK_FRAME_WIDTH * VEILLOCK_FRAME_HEIGHT * 4u)
#define VEILLOCK_FRAME_BYTES (VEILLOCK_FRAME_HEADER + VEILLOCK_FRAME_PIXELS)

/* Pagefile mapping. The feeder creates it. The DLL only opens it. */
#define VEILLOCK_MAPPING_NAME L"Local\\VeilLockFrame"

/* Argument passed to MFCreateVirtualCamera. Windows appends " Windows Virtual Camera". */
#define VEILLOCK_FRIENDLY_NAME L"VeilLock"
#define VEILLOCK_CLSID_STRING L"{C2A1E7B4-5D33-4F10-9A6E-7B18D4F02A91}"

/* Solid veil BGRA used when the mapping is missing or the magic is wrong. */
#define VEILLOCK_VEIL_B 0x32u
#define VEILLOCK_VEIL_G 0x2Au
#define VEILLOCK_VEIL_R 0x2Au
#define VEILLOCK_VEIL_A 0xFFu

#pragma pack(push, 1)
struct VeilFrameHeader {
    char magic[4];
    uint32_t version;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t sequence;
    uint32_t size;
    uint32_t flags;
};
#pragma pack(pop)

static_assert(sizeof(VeilFrameHeader) == VEILLOCK_FRAME_HEADER, "VeilLock frame header is 32 bytes");
