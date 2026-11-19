# Mad Cat Backpack
The Mad Cat Backpack is a animation upgrade for Mr TwinkleTwinkie's Mad Cat SAOs.
 
License is MIT so do what you want with it just don't litigate me. 

Current firmware runs a loop that waits a random amount of time between 0 and 8 minutes then picks a random animation. 

Current animations:
1. classic fade out fade in (random off delay)
2. blink / wink (random length random eye (left, right, or both) 
3. lip lick rights
4. lip lick left
5. piano teeth (random number of loops) 
6. eye bobble (random number of loops)
7. talking (random number of loops) 
8. sparkles (all random) 

Animations are NOT weighted evenly. Blinking has a higher probability then the others while sparkles has the least. 

Total code space use is ~36% so plenty of space for more animations if wanted. 

**NOTE** 
- When running off 5V power the LEDs are borderline too bright. Replace the 200 ohm resistors with a larger value to reduce brightness.

## KiCad
This is a KiCad 5.0 project. 
PCBs are also posed on OSHpark here: https://www.oshpark.com/shared_projects/GfiURq3q

## MplabX
This is a mplabX 5.05 project. All programming / debug was done with a PicKit4.
The firmware source is all contained in mad_cat_backpack_v0.asm 
If you just want to program a backpack using mad_cat_backpack.X.production.hex in microchip IPE is the fastest way. 

## Documentation
There is not much for documentation on this one. 

First you need a Mad Cat SAO from Mr TwinkleTwinkie:
- https://www.tindie.com/products/twinkletwinkie/twinkletwinkies-badgelife-sao-add-on-4/
- https://hackaday.io/project/159523-mad-cat

Next you need a backpack PCB:
- https://www.oshpark.com/shared_projects/GfiURq3q

Parts list for the backpack are:
 - 1x PIC16F1503-I/SL https://www.digikey.com/product-detail/en/microchip-technology/PIC16F1503-I-SL/PIC16F1503-I-SL-ND/2772041
 - 1x 10uF 10V or greater 0805 ceramic cap https://www.digikey.com/product-detail/en/samsung-electro-mechanics/CL21A106KPFNNNG/1276-6456-1-ND/5958084
 - 8x 200 ohm 0805 resistors (see note above about brightness) https://www.digikey.com/product-detail/en/yageo/AC0805JR-07200RL/YAG3769CT-ND/6006618
 - Optional 1x UJ2-MBH-1-SMT-TR mini USB jack https://www.digikey.com/product-detail/en/cui-inc/UJ2-MBH-1-SMT-TR/102-4003-1-ND/6187925
 - 8x white LEDs (reused the ones from the Mad Cat kit) 

 Assemble the back pack first. I just used a iron and tweezers to assemble mine. The LED pads ARE oversized to match the footprints on the Mad Cat. Center the LED between the pads and bridge the solder over to the terminals. Make sure the solder bridges are not taller thant the body of the LED. 

 Load the firmware using the 5 pads in the center of the board. The square pin is pin 1. 

 Test the backpack by plugging in power or USB. THe smile should dim in first then the eyes if so all is working and ready for final assembly. 

 Before final assembly the Mad Cat PCB needs to be modified. Look at Mad_Cat_modifications.jpg Cut the 4 traces marked by a red line. Make sure they are fully open. 

 Line up the backpack on the Mad Cat PCB. I used a 4 pin header though both sets of SAO holes then visually lined up the D3 and D8 leds with the solder mask holes in the Mad Cat PCB. 

 Once everything is lined up solder the 4 pads marked in blue boxes on Mad_Cat_modifications.jpg between the Mad Cat and the backpack. To do this I used a fine point soldering iron tip and some 0.5mm diameter solder. There is just enough space to get under the edge and heat the pads and the 0.5mm solder is small enough to slide between the two boards. 

 Final option step is to add yarn between the LEDs to prevent light leakage. I used some dark colored yarn and dental threaders to thread sections between all the LEDs. When in place cut the ends of the yarn off ass close to the backpack as possible and tuck the excess under the backpack. I also wrapped a piece of yarn around the edge of the backpack to keep light from spilling out behind the Mad Cat SAO.
 


Copyright (c) 2018 Peter Shabino

Permission is hereby granted, free of charge, to any person obtaining a copy of this hardware, software, and associated documentation files 
(the "Product"), to deal in the Product without restriction, including without limitation the rights to use, copy, modify, merge, publish, 
distribute, sublicense, and/or sell copies of the Product, and to permit persons to whom the Product is furnished to do so, subject to the 
following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Product.

THE PRODUCT IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE 
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION 
WITH THE PRODUCT OR THE USE OR OTHER DEALINGS IN THE PRODUCT.
