/PROG  SPSTOP
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SpStop";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 31;
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
   1:  !RAPID SearchProbe.SpStop ;
   2:  UFRAME_NUM=0 ;
   3:  UTOOL_NUM=1 ;
   4:J P[1] 22% FINE    ;
   5:  LBL[1] ;
   6:  IF (DI[1]=ON),JMP LBL[4] ;
   7:  SKIP CONDITION DI[1]=ON ;
   8:  UFRAME_NUM=0 ;
   9:  UTOOL_NUM=1 ;
  10:L P[2] 50mm/sec FINE Skip,LBL[2],PR[99]=LPOS    ;
  11:  JMP LBL[3] ;
  12:  LBL[4] ;
  13:  MESSAGE[SearchL l.16: input on] ;
  14:  PAUSE ;
  15:  JMP LBL[1] ;
  16:  LBL[2] ;
  17:  MESSAGE[SearchL l.16: no hit] ;
  18:  PAUSE ;
  19:  JMP LBL[1] ;
  20:  LBL[3] ;
  21:  R[1:nFoundY]=PR[99,2]    ;
  22:  UFRAME_NUM=0 ;
  23:  UTOOL_NUM=1 ;
  24:  PR[98]=LPOS    ;
  25:  R[2:nStopY]=PR[98,2]    ;
  26:  PR[97]=PR[99]    ;
  27:  PR[97,3]=PR[97,3]+50    ;
  28:L PR[97] 100mm/sec FINE    ;
  29:  PR[98]=LPOS    ;
  30:  R[3:nOffsY]=PR[98,2]    ;
  31:  R[4:nOffsZ]=PR[98,3]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
