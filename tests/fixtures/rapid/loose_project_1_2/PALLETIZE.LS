/PROG  PALLETIZE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Palletize";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 33;
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
   1:  !CrossArm EVALUATION copy ;
   2:  !production use needs a licence ;
   3:  !RAPID LogicAndIo.Palletize ;
   4:  UFRAME_NUM=0 ;
   5:  UTOOL_NUM=1 ;
   6:J P[1] 22% FINE    ;
   7:  WAIT DI[1]=ON    ;
   8:  LBL[1] ;
   9:  IF (R[1:nParts]>=12 OR F[1]=ON) THEN ;
  10:  JMP LBL[2] ;
  11:  ENDIF ;
  12:  R[2:nRow]=R[1:nParts] DIV 4    ;
  13:  R[3:nCol]=R[1:nParts] MOD 4    ;
  14:  IF (R[3:nCol]=0 OR DI[2]=ON) THEN ;
  15:  DO[1]=ON ;
  16:  ELSE ;
  17:  DO[1]=OFF ;
  18:  ENDIF ;
  19:  UFRAME_NUM=1 ;
  20:  UTOOL_NUM=2 ;
  21:J P[2] 18% CNT100    ;
  22:L P[3] 200mm/sec FINE    ;
  23:  DO[2]=ON ;
  24:  WAIT DO[2]=ON    ;
  25:  WAIT R[4] ;
  26:L P[2] 500mm/sec CNT74    ;
  27:  R[1:nParts]=R[1:nParts]+1    ;
  28:  IF (R[1:nParts]>=12) THEN ;
  29:  F[1]=(ON) ;
  30:  ENDIF ;
  31:  JMP LBL[1] ;
  32:  LBL[2] ;
  33:  PAUSE ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -20.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -70.000 deg,	J6=   180.000 deg
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
