/* Project-level TinyUSB configuration to override framework defaults
 * This file forces the device to expose 2 CDC interfaces and 1 HID interface.
 * Placing this in the repository `include/` ensures it is used instead of
 * the system-wide tusb_config.h provided by the framework.
 */

#ifndef _TUSB_CONFIG_H_
#define _TUSB_CONFIG_H_

#ifdef __cplusplus
 extern "C" {
#endif

//--------------------------------------------------------------------
// COMMON CONFIGURATION
//--------------------------------------------------------------------

#ifndef CFG_TUSB_MCU
 #define CFG_TUSB_MCU             OPT_MCU_RP2040
#endif

#define CFG_TUSB_RHPORT0_MODE     OPT_MODE_DEVICE
#define CFG_TUSB_OS               OPT_OS_PICO

#ifndef CFG_TUSB_DEBUG
#define CFG_TUSB_DEBUG           0
#endif

#ifndef CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_SECTION
#endif

#ifndef CFG_TUSB_MEM_ALIGN
#define CFG_TUSB_MEM_ALIGN          __attribute__ ((aligned(4)))
#endif

//--------------------------------------------------------------------
// DEVICE CONFIGURATION (project overrides)
//--------------------------------------------------------------------

#ifndef CFG_TUD_ENDPOINT0_SIZE
#define CFG_TUD_ENDPOINT0_SIZE    64
#endif

// Expose one CDC interface (debug), one native MIDI interface and one HID
#undef CFG_TUD_CDC
#define CFG_TUD_CDC              (1)

#undef CFG_TUD_HID
#define CFG_TUD_HID              (1)

// Enable native MIDI device class (for host MIDI endpoints)
#undef CFG_TUD_MIDI
#define CFG_TUD_MIDI             (1)

#undef CFG_TUD_MSC
#define CFG_TUD_MSC              (0)

#undef CFG_TUD_VENDOR
#define CFG_TUD_VENDOR           (0)

#define CFG_TUD_CDC_RX_BUFSIZE  (256)
#define CFG_TUD_CDC_TX_BUFSIZE  (256)

#define CFG_TUD_HID_EP_BUFSIZE  (64)

#ifdef __cplusplus
 }
#endif

#endif /* _TUSB_CONFIG_H_ */
