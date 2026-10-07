/PROG  KEEPPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "KeepProbe       ";
PROG_SIZE	= 705;
CREATE		= DATE 26-10-07  TIME 09:48:14;
MODIFIED	= DATE 26-10-07  TIME 09:49:08;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 6;
MEMORY_SIZE	= 1053;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
LOCAL_REGISTERS	= 0,0,0;
/MN
   1:  !RAPID KeepProbe.KeepProbe ;
   2:  UFRAME_NUM=1 ;
   3:  UTOOL_NUM=1 ;
   4:L P[1] 200mm/sec FINE    ;
   5:L P[2] 200mm/sec FINE    ;
   6:L P[3] 200mm/sec FINE    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   104.000  mm,	Y =  -150.000  mm,	Z =   197.000  mm,
	W =   180.000 deg,	P =     -.000 deg,	R =  -178.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, -1',
	X =   150.000  mm,	Y =   100.000  mm,	Z =   205.000  mm,
	W =   180.000 deg,	P =      .000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =   -50.000  mm,	Y =     0.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
