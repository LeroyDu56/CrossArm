/PROG  SPSUP
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SpSup";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 26;
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
   1:  !RAPID SearchProbe.SpSup ;
   2:  UFRAME_NUM=0 ;
   3:  UTOOL_NUM=1 ;
   4:J P[1] 22% FINE    ;
   5:  LBL[1] ;
   6:  IF (DI[1]=ON),JMP LBL[4] ;
   7:  SKIP CONDITION DI[1]=ON ;
   8:  UFRAME_NUM=0 ;
   9:  UTOOL_NUM=1 ;
  10:L P[2] 50mm/sec FINE Skip,LBL[2],PR[99]=LPOS    ;
  11:L P[2] 50mm/sec FINE    ;
  12:  JMP LBL[3] ;
  13:  LBL[4] ;
  14:  MESSAGE[SearchL l.28: input on] ;
  15:  PAUSE ;
  16:  JMP LBL[1] ;
  17:  LBL[2] ;
  18:  MESSAGE[SearchL l.28: no hit] ;
  19:  PAUSE ;
  20:  JMP LBL[1] ;
  21:  LBL[3] ;
  22:  R[5:nSupFoundY]=PR[99,2]    ;
  23:  UFRAME_NUM=0 ;
  24:  UTOOL_NUM=1 ;
  25:  PR[98]=LPOS    ;
  26:  R[6:nSupEndY]=PR[98,2]    ;
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
