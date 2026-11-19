#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();       // Invoke custom library

int scrollPosLeft = 0;   // Current scroll position for the left side
int scrollPosRight = 0;  // Current scroll position for the right side
int scrollSpeedLeft = 2;  // Scroll speed for the left side
int scrollSpeedRight = -2; // Scroll speed for the right side

unsigned long lastTimeLeft = 0;
unsigned long textSpeedLeft = 200;
unsigned long lastTimeRight = 0;
unsigned long textSpeedRight = 300;

uint16_t c64_blue = (0 << (5 + 6)) | (0 << 5) | 170;
uint16_t c64_light_blue = (0 << (5 + 6)) | (136 << 5) | 255;

void setup() {
  tft.init(); // Initialize the display
  tft.setRotation(1); // Horizontal display
  tft.fillScreen(TFT_BLACK); // Clear the screen
  tft.setTextColor(TFT_GREEN, TFT_BLACK); // Terminal-style green text
  tft.setTextSize(1); // Small text
}

void loop() {
  unsigned long currentTime = millis();

  // Vertical scrolling for the left text (scrolling up)
  if (currentTime - lastTimeLeft >= textSpeedLeft) {
    tft.fillRect(0, 0, 80, 80, TFT_BLACK);
    lastTimeLeft = currentTime;
    scrollPosLeft += scrollSpeedLeft;
    if (scrollPosLeft < 0) scrollPosLeft = 80;
    if (scrollPosLeft > 80) scrollPosLeft = 0;


    for (uint8_t j=0; j<40; j++) {
      uint8_t linePos = 0;
      for (uint8_t i=0; i<8; i++) {
        uint8_t wordl = random(0,8);
        
        tft.drawLine(linePos, 2 * (j + scrollPosLeft) % 80, linePos + wordl -1, 2 * (j + scrollPosLeft) % 80, TFT_GREEN); 
        linePos = linePos + 1 + wordl;
        
      }
    }
    tft.drawLine(0, scrollPosLeft, 80, scrollPosLeft, TFT_BLACK);
  }

  // Vertical scrolling for the right text (scrolling down)
  if (currentTime - lastTimeRight >= textSpeedRight) {
    tft.fillRect(80, 0, 80, 80, TFT_BLACK);
    lastTimeRight = currentTime;
    scrollPosRight += scrollSpeedRight;
    if (scrollPosRight < 0) scrollPosRight = 80;
    if (scrollPosRight > 80) scrollPosRight = 0;
    
    for (uint8_t j=0; j<40; j++) {
      uint8_t linePos = 0;
      for (uint8_t i=0; i<8; i++) {
        uint8_t wordl = random(0,8);
        
        tft.drawLine(80 + linePos, 2 * (j + scrollPosLeft) % 80, 80 +  linePos + wordl -1, 2 * (j + scrollPosLeft) % 80, TFT_WHITE); 
        linePos = linePos + 1 + wordl;
        
      }
    }

    tft.drawLine(80, scrollPosRight, 160, scrollPosRight, TFT_BLACK);
  }
}
