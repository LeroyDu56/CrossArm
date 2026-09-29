/PROG  POINTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 43;
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
   8:  PR[97]=P[1]    ;
   9:  CALL TURN    ;
  10:  PR[96]=P[3]    ;
  11:  CALL LIFT(25) ;
  12:  FOR R[1:r]=1 TO 2 ;
  13:  FOR R[2:c]=1 TO 2 ;
  14:  R[3:PointIndex]=R[1:r]    ;
  15:  R[3:PointIndex]=R[3:PointIndex]*2    ;
  16:  R[3:PointIndex]=R[3:PointIndex]+R[2:c]    ;
  17:  R[3:PointIndex]=R[3:PointIndex]+87    ;
  18:  UFRAME_NUM=1 ;
  19:  UTOOL_NUM=1 ;
  20:L PR[R[3]] 500mm/sec FINE    ;
  21:  PR[R[90]]=LPOS    ;
  22:  R[90]=R[90]+1    ;
  23:  PR[99]=PR[R[3]]    ;
  24:  PR[99,3]=PR[99,3]+20    ;
  25:  CALL PICKAT    ;
  26:  R[3:PointIndex]=R[1:r]    ;
  27:  R[3:PointIndex]=R[3:PointIndex]*2    ;
  28:  R[3:PointIndex]=R[3:PointIndex]+R[2:c]    ;
  29:  R[3:PointIndex]=R[3:PointIndex]+87    ;
  30:  PR[95]=PR[R[3]]    ;
  31:  PR[95,1]=5    ;
  32:  PR[95,2]=0    ;
  33:  PR[95,3]=(-15)    ;
  34:  PR[95,4]=0    ;
  35:  PR[95,5]=0    ;
  36:  PR[95,6]=20    ;
  37:  UFRAME_NUM=1 ;
  38:  UTOOL_NUM=1 ;
  39:L PR[R[3]] 500mm/sec FINE Tool_Offset,PR[95]    ;
  40:  PR[R[90]]=LPOS    ;
  41:  R[90]=R[90]+1    ;
  42:  ENDFOR ;
  43:  ENDFOR ;
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
