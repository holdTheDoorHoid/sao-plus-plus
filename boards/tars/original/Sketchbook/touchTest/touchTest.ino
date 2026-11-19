#include "TouchyTouch.h"

const int touch_threshold_adjust = 300;

const int touch_pins[] = {13, 12, 11, 10, 9, 8 };
const int touch_count = sizeof(touch_pins) / sizeof(int);

#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();       // Invoke custom library


TouchyTouch touches[touch_count];
uint16_t colors[] = {
  TFT_RED,
  TFT_BLUE,
  TFT_GREEN,
  TFT_CYAN,
  TFT_ORANGE,
  TFT_PINK
};


#include <PWMAudio.h>
#include "wav.h"
// The sample pointers
const int16_t *start = (const int16_t *)out_raw;
const int16_t *p = start;

// Create the PWM audio device on GPIO 1.   Hook amp/speaker between GPIO1 and convenient GND.
PWMAudio pwm(1);

unsigned int count = 0;

void cb() {
  while (pwm.availableForWrite()) {
    pwm.write(*p++);
    count += 2;
    if (count >= sizeof(out_raw)) {
      // reset and fuck off
      count = 0;
      p = start;
      break;
    }
  }
}


void setup() {

  Serial.begin(115200);
  Serial.println("picotouch");

  tft.init(); // Initialize the display
  tft.setRotation(3); // Horizontal display
  tft.fillScreen(TFT_BLACK); // Clear the screen
  // tft.setTextColor(charCol, lime); // Terminal-style green text
  

  // delay to let power stabilize a little so touch calibration read goes okay
  delay(1000);

  // Touch buttons
  for (int i = 0; i < touch_count; i++) {
    touches[i].begin( touch_pins[i] );
    touches[i].threshold += touch_threshold_adjust; // make a bit more noise-proof
  }
}

void loop() {
  // key handling
  for ( int i = 0; i < touch_count; i++) {
    touches[i].update();
    if ( touches[i].rose() ) { 
      tft.fillScreen(colors[i]); 
      Serial.print(i); 
      Serial.println(" rose"); 
      
      pwm.onTransmit(cb);
      pwm.begin(44100);

      }
     if ( touches[i].fell() ) {tft.fillScreen(TFT_BLACK); Serial.print(i); Serial.println(" fell"); }
  }
}
