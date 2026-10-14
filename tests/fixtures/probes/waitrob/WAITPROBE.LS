/PROG  WAITPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "WaitProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 25;
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
   1:  !RAPID WaitProbe.WaitProbe ;
   2:  R[1:nDone]=0    ;
   3:  UFRAME_NUM=0 ;
   4:  UTOOL_NUM=1 ;
   5:J P[1] 22% FINE    ;
   6:L P[2] 100mm/sec CNT100    ;
   7:  PR[99]=LPOS    ;
   8:L P[1] 1000mm/sec FINE    ;
   9:L P[2] 100mm/sec CNT100    ;
  10:  !WaitRob InPos: stop on the point ;
  11:  PR[98]=LPOS    ;
  12:  PR[98]=PR[98]-PR[98]    ;
  13:L PR[98] 100mm/sec FINE INC    ;
  14:  PR[97]=LPOS    ;
  15:L P[1] 1000mm/sec FINE    ;
  16:  CALL TOCORNER    ;
  17:  !WaitRob ZeroSpeed: stop on the point ;
  18:  PR[98]=LPOS    ;
  19:  PR[98]=PR[98]-PR[98]    ;
  20:L PR[98] 100mm/sec FINE INC    ;
  21:  UFRAME_NUM=0 ;
  22:  UTOOL_NUM=1 ;
  23:  PR[96]=LPOS    ;
  24:L P[3] 100mm/sec FINE    ;
  25:  R[1:nDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -200.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1400.000  mm,	Y =  -200.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1400.000  mm,	Y =   200.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
/END
