/PROG  PALLETIZE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Palletize       ";
PROG_SIZE	= 1079;
CREATE		= DATE 26-09-18  TIME 12:13:32;
MODIFIED	= DATE 26-09-18  TIME 12:13:32;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 31;
MEMORY_SIZE	= 1459;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
LOCAL_REGISTERS	= 0,0,0;
/MN
   1:  !RAPID LogicAndIo.Palletize ;
   2:  UFRAME_NUM=0 ;
   3:  UTOOL_NUM=1 ;
   4:J P[1] 50% FINE    ;
   5:  WAIT DI[1]=ON    ;
   6:  LBL[1] ;
   7:  IF (R[1:nParts]>=12 OR F[1]=ON) THEN ;
   8:  JMP LBL[2] ;
   9:  ENDIF ;
  10:  R[2:nRow]=R[1:nParts] DIV 4    ;
  11:  R[3:nCol]=R[1:nParts] MOD 4    ;
  12:  IF (R[3:nCol]=0 OR DI[2]=ON) THEN ;
  13:  DO[1]=ON ;
  14:  ELSE ;
  15:  DO[1]=OFF ;
  16:  ENDIF ;
  17:  UFRAME_NUM=1 ;
  18:  UTOOL_NUM=2 ;
  19:J P[2] 40% CNT50    ;
  20:L P[3] 200mm/sec FINE    ;
  21:  DO[2]=ON ;
  22:  WAIT DO[2]=ON    ;
  23:  WAIT R[4] ;
  24:L P[2] 500mm/sec CNT20    ;
  25:  R[1:nParts]=R[1:nParts]+1    ;
  26:  IF (R[1:nParts]>=12) THEN ;
  27:  F[1]=(ON) ;
  28:  ENDIF ;
  29:  JMP LBL[1] ;
  30:  LBL[2] ;
  31:  PAUSE ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -20.000 deg,	J3=    20.000 deg,
	J4=     0.000 deg,	J5=    70.000 deg,	J6=     0.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   500.000  mm,	Y =  -300.000  mm,	Z =   550.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =    90.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   500.000  mm,	Y =  -300.000  mm,	Z =   400.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =    90.000 deg
};
/END
