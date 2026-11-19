#include "TouchyTouch.h"

#define _PWM_LOGLEVEL_        4
#include "RP2040_PWM.h"

//creates pwm instance
RP2040_PWM* PWM_Instance;

float frequency = 440.0f;
float frequencies[] = {261.63f, 293.66f, 329.63f, 349.23f, 392.0f, 440.0f };
float dutyCycle = 30.0f;
boolean isPlaying[6];
boolean noteChanged = false;
boolean notePlaying = false;

const int touch_threshold_adjust = 300;

int button_A = 8, button_u = 10, button_B = 13, button_l = 9, button_d = 11, button_r = 12;
const int touch_pins[] = {button_A, button_u, button_B, button_l, button_d, button_r};
const int touch_count = sizeof(touch_pins) / sizeof(int);



uint8_t ledPin = 7;

#include <TFT_eSPI.h> // Hardware-specific library
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();       // Invoke custom library

#define pinToUseA      0     // PWM1A
#define pinToUseB      1     // PWM1A

void printPWMInfo(RP2040_PWM* PWM_Instance)
{
  uint32_t div = PWM_Instance->get_DIV();
  uint32_t top = PWM_Instance->get_TOP();

  Serial.print("Actual PWM Frequency = ");
  Serial.println(PWM_Instance->getActualFreq());

  PWM_LOGDEBUG5("TOP =", top, ", DIV =", div, ", CPU_freq =", PWM_Instance->get_freq_CPU());
}


TouchyTouch touches[touch_count];
uint16_t colors[] = {
  TFT_RED,
  TFT_YELLOW,
  TFT_GREEN,
  TFT_BLUE,
  TFT_PURPLE,
  TFT_WHITE
};

unsigned int count = 0;


int32_t oy = 8;
int32_t ox = 16;
int good_orange = tft.color565(255, 130, 0); // #ff8200
// int border_orange = tft.color565(255, 143, 26 ); // ff8f1a
int border_orange = tft.color565(255, 151, 0); // (245, 130, 10  ); // ff8f1a
// rgb(255,151,0)

uint8_t textSize = 1; // 2
uint8_t textOffset = 7; // 3

uint8_t menu_offset = 0;
uint8_t menu_selection = 0;
#define menu_length 5

char menu [menu_length][13] = {
  //"123456789012345678901234567890
  "TV-B-Gone",    // 0
  "Tesla-B-Gone", // 1
  "Trolololo",    // 2
  "bingo",        // 3
  "Piano"         // 4
};



void setup() {

  Serial.begin(115200);
  Serial.println("picotouch");

  tft.init(); // Initialize the display
  tft.setRotation(1); // Horizontal display
  tft.fillScreen(TFT_BLACK); // Clear the screen

  tft.setTextSize(textSize);
  tft.setTextColor(TFT_BLACK);
  tft.setTextWrap(true);
  // tft.setTextColor(charCol, lime); // Terminal-style green text


  // delay to let power stabilize a little so touch calibration read goes okay
  delay(1000);

  // Touch buttons
  for (int i = 0; i < touch_count; i++) {
    touches[i].begin( touch_pins[i] );
    touches[i].threshold += touch_threshold_adjust; // make a bit more noise-proof
  }

  // Use just one of these 2 for a pair
  // assigns pinToUseA, with frequency of 200 Hz and a duty cycle of 0%
  PWM_Instance = new RP2040_PWM(pinToUseA, frequency, 0);
  // assigns pinToUseB, with frequency of 200 Hz and a duty cycle of 0%
  //PWM_Instance = new RP2040_PWM(pinToUseB, frequency, 0);

  PWM_Instance->setPWMPushPull(pinToUseA, pinToUseB, frequency, 0);

  drawMenu();
}

uint8_t modeOfTars = 0;
uint8_t modeKeyboard = 4;
unsigned long keyboardTimer = 0;
unsigned long keyboardTimeOut = 10000;


void loop() {

  if (modeOfTars == modeKeyboard) {
    musicKeyboard();
    if (millis() - keyboardTimer > keyboardTimeOut) {
      modeOfTars = 0;
      drawMenu();
    }
  }
  else {

    for ( uint8_t i = 0; i < touch_count; i++) {
      touches[i].update();


      if ( touches[i].rose() ) {
        if (touch_pins[i] == button_A) {
          modeOfTars = menu_offset;
          if (modeOfTars == modeKeyboard){
            keyboardTimer = millis();
          }
        }

        if (touch_pins[i] == button_u) {
          if (menu_offset > 0) {
            menu_offset--;
          }
          else {
            menu_offset = menu_length - 1;
          }
          clickSound();
          drawMenu();
        }

        if (touch_pins[i] == button_d) {

          if (menu_offset < menu_length - 1) {
            menu_offset++;
          }
          else {
            menu_offset = 0;
          }
          clickSound();
          drawMenu();
        }
      }
      if ( touches[i].fell() ) {
      }
    }
  }
}

void clickSound(){
  PWM_Instance->enablePWM();
  PWM_Instance->setPWMPushPull(pinToUseA, pinToUseB, 1000.0f, dutyCycle);
  delay(5);
  PWM_Instance->disablePWM();
  delay(15);
}

void musicKeyboard() {
  // key handling
  for ( uint8_t i = 0; i < touch_count; i++) {
    touches[i].update();
    if ( touches[i].rose() ) {
      isPlaying[i] = true;
      noteChanged = true;
    }
    if ( touches[i].fell() ) {
      isPlaying[i] = false;
      noteChanged = true;
    }
  }

  if (noteChanged) {
    noteChanged = false;
    notePlaying = false;
    for (uint8_t i = 0; i < 6; i++) {
      if (isPlaying[i]) {
        PWM_Instance->enablePWM();
        PWM_Instance->setPWMPushPull(pinToUseA, pinToUseB, frequencies[i] * 3, dutyCycle);
        notePlaying = true;
        tft.fillScreen(colors[i]);
        keyboardTimer = millis();
      }
    }
    
    if (!notePlaying) {
      PWM_Instance->disablePWM();
      tft.fillScreen(TFT_BLACK);
    }
  }
}

void drawMenu() {
  Serial.println(menu_offset);
  tft.fillScreen(border_orange);
  tft.fillRect(ox, oy, 128, 64, good_orange);

  // center thingy
  tft.fillRoundRect(ox,   oy + 22,    128 - 4,    22,   3, TFT_BLACK);
  tft.fillRoundRect(ox + 1, oy + 22 + 1,  128 - 4 - 4,  22 - 4, 2, good_orange);

  // icons
  tft.fillRoundRect(ox + 2, oy + 2,    16, 16, 2, TFT_BLACK);
  tft.fillRoundRect(ox + 2, oy + 2 + 22, 16, 16, 2, TFT_BLACK);
  tft.fillRoundRect(ox + 2, oy + 2 + 44, 16, 16, 2, TFT_BLACK);

  int m1 = menu_offset - 1;
  int m2 = menu_offset;
  int m3 = menu_offset + 1;

  if (m1 < 0) m1 = menu_length - 1;
  if (m3 == menu_length) m3 = 0;
  // menu_length

  // write menu bits
  tft.setCursor(ox + 23, oy + textOffset);
  tft.print(menu[m1]);

  tft.setCursor(ox + 23, oy + 22 + textOffset);
  tft.print(menu[m2]);

  tft.setCursor(ox + 23, oy + 44 + textOffset);
  tft.print(menu[m3]);
}
