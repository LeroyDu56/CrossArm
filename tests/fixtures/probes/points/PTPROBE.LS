/PROG  PTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "point probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 14;
MEMORY_SIZE	= 0;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !CrossArm point probe ;
   2:  PR[100]=P[1]    ;
   3:  UTOOL[1]=PR[100] ;
   4:  PR[100]=P[2]    ;
   5:  UFRAME[1]=PR[100] ;
   6:  PR[49]=P[3]    ;
   7:  UTOOL[9]=PR[49] ;
   8:  UFRAME_NUM=0 ;
   9:  UTOOL_NUM=9 ;
  10:J P[4] 10% FINE    ;
  11:  R[90]=51    ;
  12:  CALL POINTPROBE    ;
  13:  R[90]=71    ;
  14:  CALL POINTDIRECT    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    10.000  mm,	Y =    -5.000  mm,	Z =   120.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -150.000  mm,	Z =   650.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    10.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 9,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
/END
