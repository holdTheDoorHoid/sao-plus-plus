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
LIBS:BobOmb_PCB-cache
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
U 1 1 5B347052
P 5475 2325
F 0 "X1" H 5575 2125 60  0000 C CNN
F 1 "Badgelife_shitty_connector" V 6175 2325 60  0000 C CNN
F 2 "badgelife:Badgelife-Shitty-2x2" H 5475 2325 60  0001 C CNN
F 3 "" H 5475 2325 60  0001 C CNN
	1    5475 2325
	0    -1   -1   0   
$EndComp
$Comp
L LED D1
U 1 1 5B3470C6
P 5500 3100
F 0 "D1" H 5500 3200 50  0000 C CNN
F 1 "LED" H 5500 3000 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5500 3100 50  0001 C CNN
F 3 "" H 5500 3100 50  0001 C CNN
	1    5500 3100
	-1   0    0    1   
$EndComp
$Comp
L LED D2
U 1 1 5B347111
P 5500 3450
F 0 "D2" H 5500 3550 50  0000 C CNN
F 1 "LED" H 5500 3350 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5500 3450 50  0001 C CNN
F 3 "" H 5500 3450 50  0001 C CNN
	1    5500 3450
	-1   0    0    1   
$EndComp
$Comp
L LED D3
U 1 1 5B347185
P 5500 3850
F 0 "D3" H 5500 3950 50  0000 C CNN
F 1 "LED" H 5500 3750 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5500 3850 50  0001 C CNN
F 3 "" H 5500 3850 50  0001 C CNN
	1    5500 3850
	-1   0    0    1   
$EndComp
$Comp
L R R1
U 1 1 5B3471B2
P 5050 3100
F 0 "R1" V 5130 3100 50  0000 C CNN
F 1 "R" V 5050 3100 50  0000 C CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 4980 3100 50  0001 C CNN
F 3 "" H 5050 3100 50  0001 C CNN
	1    5050 3100
	0    1    1    0   
$EndComp
$Comp
L R R2
U 1 1 5B347253
P 5050 4225
F 0 "R2" V 5130 4225 50  0000 C CNN
F 1 "R" V 5050 4225 50  0000 C CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 4980 4225 50  0001 C CNN
F 3 "" H 5050 4225 50  0001 C CNN
	1    5050 4225
	0    1    1    0   
$EndComp
NoConn ~ 5575 1775
NoConn ~ 5375 1775
Wire Wire Line
	5575 2675 6250 2675
Wire Wire Line
	6250 2675 6250 4225
Wire Wire Line
	6250 3100 5650 3100
Wire Wire Line
	6250 3450 5650 3450
Connection ~ 6250 3100
Wire Wire Line
	6250 3850 5650 3850
Connection ~ 6250 3450
Wire Wire Line
	5200 3100 5350 3100
Wire Wire Line
	5350 3100 5350 3850
Wire Wire Line
	4900 2675 5375 2675
Connection ~ 4900 3100
$Comp
L LED D4
U 1 1 5B3478D4
P 5500 4225
F 0 "D4" H 5500 4325 50  0000 C CNN
F 1 "LED" H 5500 4125 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5500 4225 50  0001 C CNN
F 3 "" H 5500 4225 50  0001 C CNN
	1    5500 4225
	-1   0    0    1   
$EndComp
Connection ~ 5350 3450
Wire Wire Line
	6250 4225 5650 4225
Connection ~ 6250 3850
Wire Wire Line
	5200 4225 5350 4225
Wire Wire Line
	4900 2675 4900 4225
$EndSCHEMATC
