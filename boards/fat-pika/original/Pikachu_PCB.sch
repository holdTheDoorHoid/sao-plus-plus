EESchema Schematic File Version 2
LIBS:power
LIBS:device
LIBS:transistors
LIBS:conn
LIBS:linear
LIBS:regul
LIBS:74xx
LIBS:cmos4000
LIBS:adc-dac
LIBS:memory
LIBS:xilinx
LIBS:microcontrollers
LIBS:dsp
LIBS:microchip
LIBS:analog_switches
LIBS:motorola
LIBS:texas
LIBS:intel
LIBS:audio
LIBS:interface
LIBS:digital-audio
LIBS:philips
LIBS:display
LIBS:cypress
LIBS:siliconi
LIBS:opto
LIBS:atmel
LIBS:contrib
LIBS:valves
LIBS:badgelife_shitty_connector
LIBS:Pikachu_PCB-cache
EELAYER 25 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title ""
Date ""
Rev ""
Comp ""
Comment1 ""
Comment2 ""
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L Badgelife_shitty_connector X1
U 1 1 5AFB2BBC
P 5325 2250
F 0 "X1" H 5425 2050 60  0000 C CNN
F 1 "Badgelife_shitty_connector" V 6025 2250 60  0000 C CNN
F 2 "badgelife:Badgelife-Shitty-2x2" H 5325 2250 60  0001 C CNN
F 3 "" H 5325 2250 60  0001 C CNN
	1    5325 2250
	0    -1   -1   0   
$EndComp
NoConn ~ 5225 1700
NoConn ~ 5425 1700
$Comp
L LED D1
U 1 1 5AFB2D16
P 5300 3025
F 0 "D1" H 5300 3125 50  0000 C CNN
F 1 "LED" H 5300 2925 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5300 3025 50  0001 C CNN
F 3 "" H 5300 3025 50  0001 C CNN
	1    5300 3025
	-1   0    0    1   
$EndComp
$Comp
L LED D2
U 1 1 5AFB2E05
P 5300 3450
F 0 "D2" H 5300 3550 50  0000 C CNN
F 1 "LED" H 5300 3350 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5300 3450 50  0001 C CNN
F 3 "" H 5300 3450 50  0001 C CNN
	1    5300 3450
	-1   0    0    1   
$EndComp
Wire Wire Line
	4725 2600 4725 3450
Wire Wire Line
	4725 3025 5150 3025
Wire Wire Line
	4725 3450 5150 3450
Connection ~ 4725 3025
Wire Wire Line
	5425 2600 5900 2600
Wire Wire Line
	5900 2600 5900 3450
Wire Wire Line
	5900 3025 5450 3025
Wire Wire Line
	5900 3450 5450 3450
Connection ~ 5900 3025
$Comp
L R R1
U 1 1 5B0F88E1
P 4975 2600
F 0 "R1" V 5055 2600 50  0000 C CNN
F 1 "R" V 4975 2600 50  0000 C CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 4905 2600 50  0001 C CNN
F 3 "" H 4975 2600 50  0001 C CNN
	1    4975 2600
	0    1    1    0   
$EndComp
Wire Wire Line
	4725 2600 4825 2600
Wire Wire Line
	5125 2600 5225 2600
$EndSCHEMATC
