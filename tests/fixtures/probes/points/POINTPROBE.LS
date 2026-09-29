/PROG  POINTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 23;
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
   1:  !RAPID PointProbe.PointProbe ;
   2:  PR[99]=P[1]    ;
   3:  CALL PICKAT    ;
   4:  PR[99]=P[2]    ;
   5:  CALL PICKAT    ;
   6:  PR[98]=P[3]    ;
   7:  CALL TWICE    ;
   8:  FOR R[1:r]=1 TO 2 ;
   9:  FOR R[2:c]=1 TO 2 ;
  10:  R[3:PointIndex]=R[1:r]    ;
  11:  R[3:PointIndex]=R[3:PointIndex]*2    ;
  12:  R[3:PointIndex]=R[3:PointIndex]+R[2:c]    ;
  13:  R[3:PointIndex]=R[3:PointIndex]+90    ;
  14:  UFRAME_NUM=1 ;
  15:  UTOOL_NUM=1 ;
  16:L PR[R[3]] 500mm/sec FINE    ;
  17:  PR[R[90]]=LPOS ;
  18:  R[90]=R[90]+1    ;
  19:  PR[99]=PR[R[3]]    ;
  20:  PR[99,3]=PR[99,3]+20    ;
  21:  CALL PICKAT    ;
  22:  ENDFOR ;
  23:  ENDFOR ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   170.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
