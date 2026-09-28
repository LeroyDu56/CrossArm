/PROG  SETUP_FRAMES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm frames";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 20;
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
   1:  !CrossArm: tool and user frames ;
   2:  !of the ABB backup ;
   3:  !PR[100] is overwritten ;
   4:  MESSAGE[Overwrites UTOOL/UFRAME] ;
   5:  PAUSE ;
   6:  !UTOOL[1] tSetA ;
   7:  PR[100]=P[1]    ;
   8:  UTOOL[1]=PR[100] ;
   9:  !UTOOL[2] tSetB ;
  10:  PR[100]=P[2]    ;
  11:  UTOOL[2]=PR[100] ;
  12:  !UTOOL[3] tSetC ;
  13:  PR[100]=P[3]    ;
  14:  UTOOL[3]=PR[100] ;
  15:  !UFRAME[1] wSet1 ;
  16:  PR[100]=P[4]    ;
  17:  UFRAME[1]=PR[100] ;
  18:  !UFRAME[2] wSet2 ;
  19:  PR[100]=P[5]    ;
  20:  UFRAME[2]=PR[100] ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    12.500  mm,	Y =    -7.250  mm,	Z =   241.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -55.000  mm,	Y =    33.000  mm,	Z =   160.400  mm,
	W =     0.000 deg,	P =    45.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    80.000  mm,	Y =    90.000  mm,	Z =    95.000  mm,
	W =    27.391 deg,	P =   -12.774 deg,	R =    49.343 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   640.000  mm,	Y =  -420.000  mm,	Z =    85.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1055.000  mm,	Y =   291.755  mm,	Z =   -22.909  mm,
	W =     8.682 deg,	P =    -4.981 deg,	R =    29.622 deg
};
/END
