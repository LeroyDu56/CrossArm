/PROG  EXITPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ExitProbe";
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
   1:  !RAPID ExitProbe.ExitProbe ;
   2:  R[1:nCycles]=R[1:nCycles]+1    ;
   3:  MONITOR END IABORT ;
   4:  UFRAME_NUM=0 ;
   5:  UTOOL_NUM=1 ;
   6:J P[1] 22% FINE    ;
   7:  IF (R[1:nCycles]=1) THEN ;
   8:  MONITOR IABORT ;
   9:L P[2] 60mm/sec FINE    ;
  10:  ENDIF ;
  11:  MONITOR END IABORT ;
  12:L P[2] 200mm/sec CNT100    ;
  13:  CALL LEAVE    ;
  14:  R[2:nDone]=R[1:nCycles]    ;
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
/END
