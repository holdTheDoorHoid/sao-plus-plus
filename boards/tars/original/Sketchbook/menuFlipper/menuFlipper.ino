/*
 Adapted from the Adafruit graphicstest sketch.

 This sketch uses the GLCD font (font 1) only. Disable other fonts to make
 the sketch fit in an UNO!

 Make sure all the display driver and pin connections are correct by
 editing the User_Setup.h file in the TFT_eSPI library folder.

 Note that yield() or delay(0) must be called in long duration for/while
 loops to stop the ESP8266 watchdog triggering.

 #########################################################################
 ###### DON'T FORGET TO UPDATE THE User_Setup.h FILE IN THE LIBRARY ######
 #########################################################################

use ST7735_REDTAB160x80 for  


 */



#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();       // Invoke custom library


// uint8_t button_l=9, button_r=13, button_u=8, button_d=5, button_c=4;
uint8_t button_l=5, button_r=9, button_u=8, button_d=13, button_c=4;

uint8_t buttons[5] = {button_l, button_r, button_u, button_d, button_c};


int32_t oy = 8;
int32_t ox = 16;
int good_orange = tft.color565(255, 130, 0); // #ff8200
// int border_orange = tft.color565(255, 143, 26 ); // ff8f1a
int border_orange = tft.color565(255,151,0); // (245, 130, 10  ); // ff8f1a
// rgb(255,151,0)

uint8_t textSize = 1; // 2
uint8_t textOffset = 7; // 3

uint8_t menu_offset = 0;
uint8_t menu_selection = 0;
#define menu_length 5

char menu [menu_length][13] = {
//"123456789012345678901234567890
  "TV-B-Gone",
  "Tesla-B-Gone",
  "Trolololo",
  "bingo",
  "bongo"
};


void setup(void) {
  Serial.begin(115200);

  Serial.println(USER_SETUP_ID);
  // Use this initializer if you're using a 1.8" TFT
  tft.init();   // initialize a ST7735S chip
  tft.invertDisplay(false);
  tft.setRotation(3);
  
  tft.setTextSize(textSize);
  tft.setTextColor(TFT_BLACK);
  tft.setTextWrap(true);

  for (uint8_t i=0; i<5; i++) {
    pinMode(buttons[i], INPUT_PULLUP);
  }

  draw();
}

void loop() {

  if (digitalRead(button_u) == LOW) {
    if (menu_offset>0) menu_offset--;
    else menu_offset = menu_length-1;
    draw();
    Serial.println("button_u");
    delay(200);
    
  }
  if (digitalRead(button_d) == LOW) {
    if (menu_offset<menu_length-1) menu_offset++;
    else menu_offset = 0;
    
    draw();
    Serial.println("button_d");
    delay(200);
  }
  if (digitalRead(button_l) == LOW) {
    Serial.println("button_l");
    delay(200);
  }
  if (digitalRead(button_r) == LOW) {
    Serial.println("button_r");
    delay(200);
  }
  if (digitalRead(button_c) == LOW) {
    Serial.println("button_c");
    delay(200);
  }
}

void draw() {
  Serial.println(menu_offset);
  tft.fillScreen(border_orange);
  tft.fillRect(ox, oy, 128, 64, good_orange);

  // center thingy
  tft.fillRoundRect(ox,   oy+22,    128-4,    22,   3, TFT_BLACK);
  tft.fillRoundRect(ox+1, oy+22+1,  128-4-4,  22-4, 2, good_orange);

  // icons
  tft.fillRoundRect(ox+2, oy+2,    16, 16, 2, TFT_BLACK);
  tft.fillRoundRect(ox+2, oy+2+22, 16, 16, 2, TFT_BLACK);
  tft.fillRoundRect(ox+2, oy+2+44, 16, 16, 2, TFT_BLACK);

  int m1 = menu_offset-1;
  int m2 = menu_offset;
  int m3 = menu_offset+1;

  if (m1<0) m1 = menu_length-1;
  if (m3==menu_length) m3 = 0;
  // menu_length
  
  // write menu bits
  tft.setCursor(ox+23, oy+textOffset);
  tft.print(menu[m1]);

  tft.setCursor(ox+23, oy+22+textOffset);
  tft.print(menu[m2]);

  tft.setCursor(ox+23, oy+44+textOffset);
  tft.print(menu[m3]);
}
