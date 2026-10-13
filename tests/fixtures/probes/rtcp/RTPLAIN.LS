/PROG  RTPLAIN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "remote TCP probe: no RTCP";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 4;
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
   1:  UFRAME_NUM=1 ;
   2:  UTOOL_NUM=1 ;
   3:L P[1] 20mm/sec FINE    ;
   4:L P[2] 20mm/sec FINE    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -62.831  mm,	Y =    -6.033  mm,	Z =     6.394  mm,
	W =  -169.096 deg,	P =    -5.041 deg,	R =  -155.481 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    30.872  mm,	Y =   -39.331  mm,	Z =     0.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   165.000 deg
};
/END
