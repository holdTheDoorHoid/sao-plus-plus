

#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();       // Invoke custom library

// Text and animation variables
String textLeft = "Scrolling up! ";
String textRight = "Scrolling down! ";
int textIndexLeft = 0;
int textIndexRight = 0;
int textSpeedLeft = 150; // Speed for the left side
int textSpeedRight = 200; // Speed for the right side
unsigned long lastTimeLeft = 0;
unsigned long lastTimeRight = 0;

int scrollPosLeft = 0;   // Current scroll position for the left side
int scrollPosRight = 0;  // Current scroll position for the right side
int scrollSpeedLeft = 2;  // Scroll speed for the left side
int scrollSpeedRight = 2; // Scroll speed for the right side

void setup() {
  tft.init(); // Initialize the display
  tft.setRotation(1); // Horizontal display
  tft.fillScreen(ST7735_BLACK); // Clear the screen

  tft.setTextColor(ST7735_GREEN, ST7735_BLACK); // Terminal-style green text
  tft.setTextSize(1); // Small text
}


void loop() {
  unsigned long currentTime = millis();

  // Vertical scrolling for the left text (scrolling up)
  if (currentTime - lastTimeLeft >= textSpeedLeft) {
    // Clear the old frame
    tft.fillRect(0, 0, 80, 80, ST7735_BLACK); // Clear the left half
    
    // Scroll and animate the text vertically
    drawTypingEffect(textLeft.substring(0, textIndexLeft + 1), 5, 80 - scrollPosLeft);
    scrollPosLeft += scrollSpeedLeft; // Scroll upward
    if (scrollPosLeft >= 80) { // Reset when reaching the top
      scrollPosLeft = 0;
      textIndexLeft++;
      if (textIndexLeft >= textLeft.length()) {
        textIndexLeft = 0; // Restart typing after the text ends
      }
    }
    
    // Update the time for the left side
    lastTimeLeft = currentTime;
  }

  // Vertical scrolling for the right text (scrolling down)
  if (currentTime - lastTimeRight >= textSpeedRight) {
    // Clear the old frame
    tft.fillRect(80, 0, 80, 80, ST7735_BLACK); // Clear the right half
    
    // Scroll and animate the text vertically
    drawTypingEffect(textRight.substring(0, textIndexRight + 1), 90, scrollPosRight - 80);
    scrollPosRight += scrollSpeedRight; // Scroll downward
    if (scrollPosRight >= 80) { // Reset when reaching the bottom
      scrollPosRight = 0;
      textIndexRight++;
      if (textIndexRight >= textRight.length()) {
        textIndexRight = 0; // Restart typing after the text ends
      }
    }
    
    // Update the time for the right side
    lastTimeRight = currentTime;
  }
}

// Function to simulate text being typed in small 2x2 pixel block patterns
void drawTypingEffect(String text, int x, int y) {
  for (int i = 0; i < text.length(); i++) {
    char c = text[i];
    if (c == ' ') {
      tft.print(' '); // Space character
    } else {
      // Draw each character as a collection of 2x2 pixel blocks
      for (int row = 0; row < 4; row++) {
        for (int col = 0; col < 3; col++) {
          // Create a grid of 2x2 pixel squares
          if ((row + col) % 2 == 0) { // Create a pattern, adjust logic for more complex shapes
            tft.fillRect(x + (i * 6) + (col * 2), y + (row * 2), 2, 2, ST7735_GREEN);
          }
        }
      }
      delay(30); // Small delay to create typing effect
    }
  }
}
