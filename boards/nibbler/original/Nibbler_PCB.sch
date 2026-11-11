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
LIBS:Nibbler_PCB-cache
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
U 1 1 5B4440F4
P 5675 2350
F 0 "X1" H 5775 2150 60  0000 C CNN
F 1 "Badgelife_shitty_connector" V 6350 2350 60  0000 C CNN
F 2 "badgelife:Badgelife-Shitty-2x2" H 5675 2350 60  0001 C CNN
F 3 "" H 5675 2350 60  0001 C CNN
	1    5675 2350
	0    -1   -1   0   
$EndComp
$Comp
L R R1
U 1 1 5B444169
P 5125 2700
F 0 "R1" V 5205 2700 50  0000 C CNN
F 1 "R" V 5125 2700 50  0000 C CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 5055 2700 50  0001 C CNN
F 3 "" H 5125 2700 50  0001 C CNN
	1    5125 2700
	0    1    1    0   
$EndComp
$Comp
L LED D1
U 1 1 5B444245
P 5700 3075
F 0 "D1" H 5700 3175 50  0000 C CNN
F 1 "LED" H 5700 2975 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5700 3075 50  0001 C CNN
F 3 "" H 5700 3075 50  0001 C CNN
	1    5700 3075
	-1   0    0    1   
$EndComp
$Comp
L LED D2
U 1 1 5B4442C2
P 5700 3475
F 0 "D2" H 5700 3575 50  0000 C CNN
F 1 "LED" H 5700 3375 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5700 3475 50  0001 C CNN
F 3 "" H 5700 3475 50  0001 C CNN
	1    5700 3475
	-1   0    0    1   
$EndComp
NoConn ~ 5575 1800
NoConn ~ 5775 1800
Wire Wire Line
	5575 2700 5275 2700
Wire Wire Line
	4975 2700 4975 3850
Wire Wire Line
	4975 3075 5550 3075
Wire Wire Line
	4975 3475 5550 3475
Connection ~ 4975 3075
Wire Wire Line
	5775 2700 6300 2700
Wire Wire Line
	6300 2700 6300 3850
Wire Wire Line
	6300 3075 5850 3075
Wire Wire Line
	6300 3475 5850 3475
Connection ~ 6300 3075
$Comp
L LED D3
U 1 1 5B5381AD
P 5725 3850
F 0 "D3" H 5725 3950 50  0000 C CNN
F 1 "LED" H 5725 3750 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5725 3850 50  0001 C CNN
F 3 "" H 5725 3850 50  0001 C CNN
	1    5725 3850
	-1   0    0    1   
$EndComp
Wire Wire Line
	4975 3850 5575 3850
Connection ~ 4975 3475
Wire Wire Line
	6300 3850 5875 3850
Connection ~ 6300 3475
$EndSCHEMATC
