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
F 2 "lumpyv2:PinHeader_2x02_P2.54mm_Vertical_edit" H 4200 4950 50  0001 C CNN
F 3 "~" H 4200 4950 50  0001 C CNN
	1    4200 4950
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
F 2 "lumpyv2:LED_OSRAM_TOPLED_LxT776" H 4450 3700 50  0001 C CNN
F 3 "~" H 4450 3700 50  0001 C CNN
	1    4450 3700
	0    1    1    0   
$EndComp
Wire Wire Line
	3800 3550 3800 5050
Wire Wire Line
	3800 5050 4000 5050
Connection ~ 4000 3550
Wire Wire Line
	4000 3550 3800 3550
Wire Wire Line
	4450 3550 4000 3550
Text Notes 3850 5050 0    50   ~ 0
VCC\nGND
NoConn ~ 4500 4950
NoConn ~ 4500 5050
$Comp
L Device:R R1
U 1 1 5BA46B42
P 4000 4150
F 0 "R1" H 4070 4196 50  0000 L CNN
F 1 "R" H 4070 4105 50  0000 L CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 3930 4150 50  0001 C CNN
F 3 "~" H 4000 4150 50  0001 C CNN
	1    4000 4150
	1    0    0    -1  
$EndComp
$Comp
L Device:R R2
U 1 1 5BA46B70
P 4450 4150
F 0 "R2" H 4520 4196 50  0000 L CNN
F 1 "R" H 4520 4105 50  0000 L CNN
F 2 "Resistors_SMD:R_0805_HandSoldering" V 4380 4150 50  0001 C CNN
F 3 "~" H 4450 4150 50  0001 C CNN
	1    4450 4150
	1    0    0    -1  
$EndComp
Wire Wire Line
	4000 4300 4000 4950
Wire Wire Line
	4000 4300 4450 4300
Connection ~ 4000 4300
Wire Wire Line
	4000 4000 4000 3850
Wire Wire Line
	4450 4000 4450 3850
$EndSCHEMATC
