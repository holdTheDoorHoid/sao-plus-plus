EESchema Schematic File Version 4
EELAYER 26 0
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
L Connector_Generic:Conn_02x02_Odd_Even J1
U 1 1 5B56A1D7
P 4200 4950
F 0 "J1" H 4250 5167 50  0000 C CNN
F 1 "Conn_02x02_Odd_Even" H 4250 5076 50  0000 C CNN
F 2 "lumpy:PinHeader_2x02_P2.54mm_Vertical_edit" H 4200 4950 50  0001 C CNN
F 3 "~" H 4200 4950 50  0001 C CNN
	1    4200 4950
	1    0    0    -1  
$EndComp
$Comp
L Device:R R1
U 1 1 5B56A232
P 3950 4300
F 0 "R1" H 4020 4346 50  0000 L CNN
F 1 "R" H 4020 4255 50  0000 L CNN
F 2 "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P5.08mm_Vertical" V 3880 4300 50  0001 C CNN
F 3 "~" H 3950 4300 50  0001 C CNN
	1    3950 4300
	1    0    0    -1  
$EndComp
$Comp
L Device:LED D1
U 1 1 5B56A2CA
P 4000 3700
F 0 "D1" V 3945 3778 50  0000 L CNN
F 1 "LED" V 4036 3778 50  0000 L CNN
F 2 "LED_THT:LED_D3.0mm_FlatTop" H 4000 3700 50  0001 C CNN
F 3 "~" H 4000 3700 50  0001 C CNN
	1    4000 3700
	0    1    1    0   
$EndComp
$Comp
L Device:LED D2
U 1 1 5B56A365
P 4450 3700
F 0 "D2" V 4395 3778 50  0000 L CNN
F 1 "LED" V 4486 3778 50  0000 L CNN
F 2 "LED_THT:LED_D3.0mm_FlatTop" H 4450 3700 50  0001 C CNN
F 3 "~" H 4450 3700 50  0001 C CNN
	1    4450 3700
	0    1    1    0   
$EndComp
$Comp
L Device:LED D3
U 1 1 5B56A3E6
P 4800 3700
F 0 "D3" V 4745 3778 50  0000 L CNN
F 1 "LED" V 4836 3778 50  0000 L CNN
F 2 "LED_THT:LED_D3.0mm_FlatTop" H 4800 3700 50  0001 C CNN
F 3 "~" H 4800 3700 50  0001 C CNN
	1    4800 3700
	0    1    1    0   
$EndComp
$Comp
L Device:LED D4
U 1 1 5B56A488
P 5100 3700
F 0 "D4" V 5045 3778 50  0000 L CNN
F 1 "LED" V 5136 3778 50  0000 L CNN
F 2 "LED_THT:LED_D3.0mm_FlatTop" H 5100 3700 50  0001 C CNN
F 3 "~" H 5100 3700 50  0001 C CNN
	1    5100 3700
	0    1    1    0   
$EndComp
$Comp
L Device:LED D5
U 1 1 5B56A4F1
P 5400 3700
F 0 "D5" V 5345 3778 50  0000 L CNN
F 1 "LED" V 5436 3778 50  0000 L CNN
F 2 "LED_THT:LED_D3.0mm_FlatTop" H 5400 3700 50  0001 C CNN
F 3 "~" H 5400 3700 50  0001 C CNN
	1    5400 3700
	0    1    1    0   
$EndComp
Wire Wire Line
	4000 4950 4000 4450
Wire Wire Line
	4000 4450 3950 4450
Wire Wire Line
	3950 4150 3950 3850
Wire Wire Line
	3950 3850 4000 3850
Wire Wire Line
	4000 3850 4450 3850
Connection ~ 4000 3850
Connection ~ 4450 3850
Wire Wire Line
	4450 3850 4800 3850
Connection ~ 4800 3850
Wire Wire Line
	4800 3850 5100 3850
Connection ~ 5100 3850
Wire Wire Line
	5100 3850 5400 3850
Wire Wire Line
	5400 3550 5100 3550
Wire Wire Line
	3800 3550 3800 5050
Wire Wire Line
	3800 5050 4000 5050
Connection ~ 4000 3550
Wire Wire Line
	4000 3550 3800 3550
Connection ~ 4450 3550
Wire Wire Line
	4450 3550 4000 3550
Connection ~ 4800 3550
Wire Wire Line
	4800 3550 4450 3550
Connection ~ 5100 3550
Wire Wire Line
	5100 3550 4800 3550
Text Notes 3850 5050 0    50   ~ 0
VCC\nGND
NoConn ~ 4500 4950
NoConn ~ 4500 5050
$EndSCHEMATC
