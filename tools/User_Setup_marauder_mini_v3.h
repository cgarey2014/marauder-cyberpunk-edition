//                            USER DEFINED SETTINGS
//   Set driver type, fonts to be loaded, pins used and SPI control method etc
//
//   Marauder Mini v3 (ESP32-C5) panel configuration.
//
//   Panel: 128 x 128 ST7735, BGR order, green tab 3, backlight active low.
//   The Mini v3 shares one SPI bus between the panel and the microSD card, so
//   SD_MISO / SD_MOSI / SD_SCK in configs.h alias these three pins.
//
//   esp32_marauder/configs.h also carries TFT_* pin defines for this target.
//   Those are inherited from the older Marauder Mini / Centauri layout and do
//   not describe this board, and they are defined before this file is reached.
//   They are cleared here so the panel configuration has exactly one source and
//   the build is free of macro redefinition warnings.

#undef TFT_MISO
#undef TFT_MOSI
#undef TFT_SCLK
#undef TFT_CS
#undef TFT_DC
#undef TFT_RST
#undef TFT_BL
#undef TOUCH_CS
#undef TFT_WIDTH
#undef TFT_HEIGHT

// ##################################################################################
//
// Section 1. Call up the right driver file and any options for it
//
// ##################################################################################

#define ST7735_DRIVER                     // Marauder Mini v3

// The panel is BGR ordered; leaving this at the default swaps red and blue.
#define TFT_RGB_ORDER TFT_BGR

// ST7735 panel variant. Green tab 3 is the correct initialisation for this part.
#define ST7735_GREENTAB3

// Always define the pixel width and height in portrait orientation.
#define TFT_WIDTH  128
#define TFT_HEIGHT 128

// The backlight is switched on by driving the pin low.
#define TFT_BACKLIGHT_ON LOW

// ##################################################################################
//
// Section 2. Define the pins that are used to interface with the display here
//
// ##################################################################################

#define TFT_MISO 2
#define TFT_MOSI 7
#define TFT_SCLK 6
#define TFT_CS   23
#define TFT_DC   24
#define TFT_RST -1   // panel reset is tied to the board reset
#define TFT_BL   5
#define TOUCH_CS -1  // no touch controller on this board

// ##################################################################################
//
// Section 3. Define the fonts that are to be used here
//
// ##################################################################################

#define LOAD_GLCD    // Font 1. Original Adafruit 8 pixel font
#define LOAD_FONT2   // Font 2. Small 16 pixel high font, 96 characters
#define LOAD_FONT4   // Font 4. Medium 26 pixel high font, 96 characters
#define LOAD_FONT6   // Font 6. Large 48 pixel font, only characters 1234567890:-.apm
#define LOAD_FONT7   // Font 7. 7 segment 48 pixel font, only characters 1234567890:-.
#define LOAD_FONT8   // Font 8. Large 75 pixel font, only characters 1234567890:-.
#define LOAD_GFXFF   // FreeFonts. Include access to the Adafruit_GFX free fonts
#define SMOOTH_FONT

// ##################################################################################
//
// Section 4. Other options
//
// ##################################################################################

// A ST7735 panel becomes unreliable above roughly 27 MHz.
#define SPI_FREQUENCY        20000000
#define SPI_READ_FREQUENCY   20000000
#define SPI_TOUCH_FREQUENCY   2500000

// Transaction support is needed because the SD card shares the SPI bus.
// TFT_eSPI enables this automatically for ESP32 targets.
