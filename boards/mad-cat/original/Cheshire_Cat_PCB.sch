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
LIBS:Cheshire_Cat_PCB-cache
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
U 1 1 5B260143
P 5800 2275
F 0 "X1" H 5900 2075 60  0000 C CNN
F 1 "Badgelife_shitty_connector" V 6475 2275 60  0000 C CNN
F 2 "badgelife:Badgelife-Shitty-2x2" H 5800 2275 60  0001 C CNN
F 3 "" H 5800 2275 60  0001 C CNN
	1    5800 2275
	0    -1   -1   0   
$EndComp
NoConn ~ 5900 1725
NoConn ~ 5700 1725
$Comp
L LED D1
U 1 1 5B260227
P 5800 2875
F 0 "D1" H 5800 2975 50  0000 C CNN
F 1 "LED" H 5800 2775 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 2875 50  0001 C CNN
F 3 "" H 5800 2875 50  0001 C CNN
	1    5800 2875
	-1   0    0    1   
$EndComp
$Comp
L R R1
U 1 1 5B2606B0
P 5400 2625
F 0 "R1" V 5480 2625 50  0000 C CNN
F 1 "15" V 5400 2625 50  0000 C CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 5330 2625 50  0001 C CNN
F 3 "" H 5400 2625 50  0001 C CNN
	1    5400 2625
	0    1    1    0   
$EndComp
$Comp
L LED D2
U 1 1 5B260CC5
P 5800 3175
F 0 "D2" H 5800 3275 50  0000 C CNN
F 1 "LED" H 5800 3075 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 3175 50  0001 C CNN
F 3 "" H 5800 3175 50  0001 C CNN
	1    5800 3175
	-1   0    0    1   
$EndComp
$Comp
L LED D3
U 1 1 5B260D1D
P 5800 3475
F 0 "D3" H 5800 3575 50  0000 C CNN
F 1 "LED" H 5800 3375 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 3475 50  0001 C CNN
F 3 "" H 5800 3475 50  0001 C CNN
	1    5800 3475
	-1   0    0    1   
$EndComp
$Comp
L LED D4
U 1 1 5B260D71
P 5800 3775
F 0 "D4" H 5800 3875 50  0000 C CNN
F 1 "LED" H 5800 3675 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 3775 50  0001 C CNN
F 3 "" H 5800 3775 50  0001 C CNN
	1    5800 3775
	-1   0    0    1   
$EndComp
$Comp
L LED D5
U 1 1 5B260DC9
P 5800 4075
F 0 "D5" H 5800 4175 50  0000 C CNN
F 1 "LED" H 5800 3975 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 4075 50  0001 C CNN
F 3 "" H 5800 4075 50  0001 C CNN
	1    5800 4075
	-1   0    0    1   
$EndComp
$Comp
L LED D6
U 1 1 5B260E25
P 5800 4375
F 0 "D6" H 5800 4475 50  0000 C CNN
F 1 "LED" H 5800 4275 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 4375 50  0001 C CNN
F 3 "" H 5800 4375 50  0001 C CNN
	1    5800 4375
	-1   0    0    1   
$EndComp
$Comp
L LED D7
U 1 1 5B260E85
P 5800 4675
F 0 "D7" H 5800 4775 50  0000 C CNN
F 1 "LED" H 5800 4575 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 4675 50  0001 C CNN
F 3 "" H 5800 4675 50  0001 C CNN
	1    5800 4675
	-1   0    0    1   
$EndComp
$Comp
L LED D8
U 1 1 5B260F34
P 5800 4975
F 0 "D8" H 5800 5075 50  0000 C CNN
F 1 "LED" H 5800 4875 50  0000 C CNN
F 2 "customparts:LED_OSRAM_TOPLED_LxT776" H 5800 4975 50  0001 C CNN
F 3 "" H 5800 4975 50  0001 C CNN
	1    5800 4975
	-1   0    0    1   
$EndComp
Wire Wire Line
	5050 2625 5050 4975
Connection ~ 5050 2875
Connection ~ 5050 3175
Connection ~ 5050 3475
Connection ~ 5050 3775
Connection ~ 5050 4075
Connection ~ 5050 4375
Connection ~ 5050 4675
Wire Wire Line
	5900 2625 6550 2625
Wire Wire Line
	6550 2625 6550 4975
Wire Wire Line
	6550 2875 5950 2875
Wire Wire Line
	6550 3175 5950 3175
Connection ~ 6550 2875
Wire Wire Line
	6550 3475 5950 3475
Connection ~ 6550 3175
Wire Wire Line
	6550 3775 5950 3775
Connection ~ 6550 3475
Wire Wire Line
	6550 4075 5950 4075
Connection ~ 6550 3775
Wire Wire Line
	6550 4375 5950 4375
Connection ~ 6550 4075
Wire Wire Line
	6550 4675 5950 4675
Connection ~ 6550 4375
Wire Wire Line
	6550 4975 5950 4975
Connection ~ 6550 4675
Wire Wire Line
	5700 2625 5550 2625
Wire Wire Line
	5050 2625 5250 2625
Wire Wire Line
	5050 2875 5650 2875
Wire Wire Line
	5050 3175 5650 3175
Wire Wire Line
	5050 3475 5650 3475
Wire Wire Line
	5050 3775 5650 3775
Wire Wire Line
	5050 4075 5650 4075
Wire Wire Line
	5050 4375 5650 4375
Wire Wire Line
	5050 4675 5650 4675
Wire Wire Line
	5050 4975 5650 4975
$EndSCHEMATC
