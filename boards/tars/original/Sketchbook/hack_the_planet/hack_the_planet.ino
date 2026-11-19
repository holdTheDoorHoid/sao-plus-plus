#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();       // Invoke custom library

uint16_t lime = tft.color565(168, 168, 44); // tft.color565(168, 198, 62); // (168 << (5 + 6)) | (198 << 5) | 78;
uint16_t charCol = tft.color565(60, 65, 44); // (60 << (5 + 6)) | (65 << 5) | 44;
//uint16_t lime = tft.color565(168, 198, 62);9i // tft.color565(168, 198, 62); // (168 << (5 + 6)) | (198 << 5) | 78;
//uint16_t charCol = tft.color565(60, 65, 44); // (60 << (5 + 6)) | (65 << 5) | 44;
boolean show = false;

unsigned long lastTimeLeft = 0;
unsigned long textSpeedLeft = 1000;

void setup() {
  tft.init(); // Initialize the display
  tft.setRotation(1); // Horizontal display
  tft.fillScreen(lime); // Clear the screen
  tft.setTextColor(charCol, lime); // Terminal-style green text
  
}

void loop() {
  unsigned long currentTime = millis();

  // Vertical scrolling for the left text (scrolling up)
  if (currentTime - lastTimeLeft >= textSpeedLeft) {
    show = !show;

    tft.setTextSize(1); // Small text
    
    tft.setCursor(2, 2, 1);
    tft.println("vodafone");
    
    // antenna?
    tft.fillRect(96, 2, 6, 2, charCol);
    tft.fillRect(97, 4, 4, 2, charCol);
    tft.fillRect(98, 6, 2, 4, charCol);

    // N 
    tft.setCursor(108, 2, 1);
    tft.println("N");

    // boxes
    for (uint8_t i=0; i<4; i++)
    {
      tft.drawRect(152 - 8*i, 2, 6, 6, charCol);
      tft.drawRect(153 - 8*i, 3, 4, 4, charCol);
    }

    // message
    tft.setTextSize(2);
    
    tft.setCursor(2, 24, 1);
    tft.println("GRAND CENTRAL"); // 13*6*2 = 156
    tft.setCursor(56, 40, 1);
    tft.println("HACK");

    
    if (show) {
      tft.setCursor(20, 56, 1);
      tft.println("THE PLANET");
    }
    else {
      tft.fillRect(20, 56, 120, 16, lime);
    }
    
    lastTimeLeft = currentTime;
  }
}
