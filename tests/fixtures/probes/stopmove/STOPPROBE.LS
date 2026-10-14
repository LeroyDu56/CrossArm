/PROG  STOPPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "StopProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 27;
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
   1:  !RAPID StopProbe.StopProbe ;
   2:  R[1:nPaused]=0    ;
   3:  R[2:nHolds]=0    ;
   4:  R[3:nEnables]=0    ;
   5:  R[4:nDone]=0    ;
   6:  MONITOR END ISTOPA ;
   7:  MONITOR END IHOLDB ;
   8:  MONITOR END IENABLE ;
   9:  UFRAME_NUM=0 ;
  10:  UTOOL_NUM=1 ;
  11:J P[1] 22% FINE    ;
  12:  MONITOR ISTOPA ;
  13:L P[2] 100mm/sec FINE    ;
  14:  MONITOR END ISTOPA ;
  15:L P[1] 1000mm/sec FINE    ;
  16:L P[2] 100mm/sec CNT100    ;
  17:  CALL CA_STOPMOVE(1,0) ;
  18:  WAIT   2.00(sec) ;
  19:  CALL CA_STOPMOVE(0,0) ;
  20:  MONITOR IHOLDB ;
  21:  MONITOR IENABLE ;
  22:  UFRAME_NUM=0 ;
  23:  UTOOL_NUM=1 ;
  24:L P[3] 100mm/sec FINE    ;
  25:  MONITOR END IHOLDB ;
  26:  MONITOR END IENABLE ;
  27:  R[4:nDone]=1    ;
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
