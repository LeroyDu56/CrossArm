/PROG  POINTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 55;
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
  12:  PR[95]=P[4]    ;
  13:  CALL WITHTOOL(2,2) ;
  14:  PR[95]=P[5]    ;
  15:  CALL WITHTOOL(1,1) ;
  16:  FOR R[1:r]=1 TO 2 ;
  17:  FOR R[2:c]=1 TO 2 ;
  18:  R[3:PointIndex]=R[1:r]    ;
  19:  R[3:PointIndex]=R[3:PointIndex]*2    ;
  20:  R[3:PointIndex]=R[3:PointIndex]+R[2:c]    ;
  21:  R[3:PointIndex]=R[3:PointIndex]+86    ;
  22:  UFRAME_NUM=1 ;
  23:  UTOOL_NUM=1 ;
  24:L PR[R[3]] 500mm/sec FINE    ;
  25:  UFRAME_NUM=0 ;
  26:  UTOOL_NUM=9 ;
  27:  PR[R[90]]=LPOS    ;
  28:  R[90]=R[90]+1    ;
  29:  UFRAME_NUM=1 ;
  30:  UTOOL_NUM=1 ;
  31:  PR[99]=PR[R[3]]    ;
  32:  PR[99,3]=PR[99,3]+20    ;
  33:  CALL PICKAT    ;
  34:  R[3:PointIndex]=R[1:r]    ;
  35:  R[3:PointIndex]=R[3:PointIndex]*2    ;
  36:  R[3:PointIndex]=R[3:PointIndex]+R[2:c]    ;
  37:  R[3:PointIndex]=R[3:PointIndex]+86    ;
  38:  PR[94]=PR[R[3]]    ;
  39:  PR[94,1]=5    ;
  40:  PR[94,2]=0    ;
  41:  PR[94,3]=(-15)    ;
  42:  PR[94,4]=0    ;
  43:  PR[94,5]=0    ;
  44:  PR[94,6]=20    ;
  45:  UFRAME_NUM=1 ;
  46:  UTOOL_NUM=1 ;
  47:L PR[R[3]] 500mm/sec FINE Tool_Offset,PR[94]    ;
  48:  UFRAME_NUM=0 ;
  49:  UTOOL_NUM=9 ;
  50:  PR[R[90]]=LPOS    ;
  51:  R[90]=R[90]+1    ;
  52:  UFRAME_NUM=1 ;
  53:  UTOOL_NUM=1 ;
  54:  ENDFOR ;
  55:  ENDFOR ;
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
P[4]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   260.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
