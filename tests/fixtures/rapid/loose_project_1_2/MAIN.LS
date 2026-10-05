/PROG  MAIN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "main";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 18;
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
   3:  !RAPID PickAndPlace.main ;
   4:  UFRAME_NUM=0 ;
   5:  UTOOL_NUM=1 ;
   6:J P[1] 22% FINE    ;
   7:  UTOOL_NUM=3 ;
   8:J P[2] 22% CNT92    ;
   9:  LBL[1] ;
  10:  IF (DI[4]=ON) THEN ;
  11:  CALL PICK    ;
  12:  ENDIF ;
  13:  FOR R[7:i]=1 TO 3 ;
  14:  R[8:nSlot]=R[7:i]    ;
  15:  CALL PLACE    ;
  16:  ENDFOR ;
  17:  R[9:nCycles]=R[9:nCycles]+1    ;
  18:  JMP LBL[1] ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -30.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 3,		CONFIG : 'N U T, 0, 0, 1',
	X =   600.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
