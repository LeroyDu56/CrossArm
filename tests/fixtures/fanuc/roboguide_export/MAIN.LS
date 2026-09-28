/PROG  MAIN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "main            ";
PROG_SIZE	= 792;
CREATE		= DATE 26-09-18  TIME 12:01:46;
MODIFIED	= DATE 26-09-18  TIME 12:01:46;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 16;
MEMORY_SIZE	= 1248;
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
   1:  !RAPID PickAndPlace.main ;
   2:  UFRAME_NUM=0 ;
   3:  UTOOL_NUM=1 ;
   4:J P[1] 50% FINE    ;
   5:  UTOOL_NUM=2 ;
   6:J P[2] 50% CNT50    ;
   7:  LBL[1] ;
   8:  IF (DI[1]=ON) THEN ;
   9:  CALL PICK    ;
  10:  ENDIF ;
  11:  FOR R[1:i]=1 TO 3 ;
  12:  R[2:nSlot]=R[1:i]    ;
  13:  CALL PLACE    ;
  14:  ENDFOR ;
  15:  R[3:nCycles]=R[3:nCycles]+1    ;
  16:  JMP LBL[1] ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -30.000 deg,	J3=    30.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   600.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
