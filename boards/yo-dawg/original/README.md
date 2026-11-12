# Yo Dawg, I heard you like add-ons on your badges?
With the hackaday supercon add-on contest in 2024, 
there came a lot of self-inflicted pressure of doing something great with the I2C pins and slap something smart on the PCBs. 
This sounded great, but what if you just want to do a small meme or have some RGB LEDs blinking?
What if you feel like that is not worthy of being a simple add-on made for the contest?

## design choices
To be safe with distance between badges, I decided on having the size constrained to 19mm x 19mm and using a 1.27mm pin header to connect GND-VCC-GND to the simple add-on mainboard. 
This header size was the wrong decision as it is a pain to solder - but it's the standard now!

![Screenshot of KiCad render](https://github.com/davedarko/YoDawgSAO/blob/main/reference/Yo-Dawg-Heard-You_render.png?raw=true)
