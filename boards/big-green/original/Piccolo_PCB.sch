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
U 1 1 5B16C1EA
P 5450 2400
F 0 "X1" H 5550 2200 60  0000 C CNN
F 1 "Badgelife_shitty_connector" V 6150 2400 60  0000 C CNN
F 2 "badgelife:Badgelife-Shitty-2x2" H 5450 2400 60  0001 C CNN
F 3 "" H 5450 2400 60  0001 C CNN
	1    5450 2400
	0    -1   -1   0   
$EndComp
$Comp
L R R1
U 1 1 5B16C22C
P 5100 2750
F 0 "R1" V 5180 2750 50  0000 C CNN
F 1 "R51" V 5100 2750 50  0000 C CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 5030 2750 50  0001 C CNN
F 3 "" H 5100 2750 50  0001 C CNN
	1    5100 2750
	0    -1   -1   0   
$EndComp
$Comp
L LED D1
U 1 1 5B16C344
P 5450 3100
F 0 "D1" H 5450 3200 50  0000 C CNN
F 1 "LED" H 5450 3000 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5450 3100 50  0001 C CNN
F 3 "" H 5450 3100 50  0001 C CNN
	1    5450 3100
	-1   0    0    1   
$EndComp
$Comp
L LED D2
U 1 1 5B16C3B7
P 5450 3500
F 0 "D2" H 5450 3600 50  0000 C CNN
F 1 "LED" H 5450 3400 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5450 3500 50  0001 C CNN
F 3 "" H 5450 3500 50  0001 C CNN
	1    5450 3500
	-1   0    0    1   
$EndComp
Wire Wire Line
	4850 2750 4850 3500
Wire Wire Line
	4850 3100 5300 3100
Wire Wire Line
	4850 3500 5300 3500
Connection ~ 4850 3100
Wire Wire Line
	4950 2750 4850 2750
Wire Wire Line
	5250 2750 5350 2750
Wire Wire Line
	5550 2750 6050 2750
Wire Wire Line
	6050 2750 6050 3500
Wire Wire Line
	6050 3100 5600 3100
Wire Wire Line
	6050 3500 5600 3500
Connection ~ 6050 3100
NoConn ~ 5550 1850
NoConn ~ 5350 1850
$EndSCHEMATC
