/PROG  PRPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PrProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 24;
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
   1:  !RAPID PointRefProbe.PrProbe ;
   2:  R[2:prY1]=0    ;
   3:  R[3:prY2]=0    ;
   4:  R[4:prZ]=0    ;
   5:  R[5:prX]=0    ;
   6:  R[1:prSteps]=0    ;
   7:  UFRAME_NUM=0 ;
   8:  UTOOL_NUM=1 ;
   9:J P[1] 22% FINE    ;
  10:  PR[97]=P[2]    ;
  11:J PR[97] 22% FINE    ;
  12:  PR[99]=PR[97]    ;
  13:  CALL PRSHIFT    ;
  14:  PR[97]=PR[99]    ;
  15:  PR[99]=PR[97]    ;
  16:  CALL PRSHIFT    ;
  17:  PR[97]=PR[99]    ;
  18:  R[2:prY1]=PR[97,2]    ;
  19:  PR[98]=PR[97]    ;
  20:  CALL PRLIFT(100) ;
  21:  PR[97]=PR[98]    ;
  22:  R[3:prY2]=PR[97,2]    ;
  23:  R[4:prZ]=PR[97,3]    ;
  24:  R[5:prX]=PR[97,1]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
