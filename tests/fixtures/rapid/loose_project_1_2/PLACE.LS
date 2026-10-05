/PROG  PLACE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Place";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 30;
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
   3:  !RAPID PickAndPlace.Place ;
   4:  PR[99]=P[1]    ;
   5:  R[10:NumberIndex]=R[8:nSlot]    ;
   6:  R[10:NumberIndex]=R[10:NumberIndex]+197    ;
   7:  PR[99,1]=PR[99,1]+R[R[10]]    ;
   8:  PR[99,3]=PR[99,3]+(-400)    ;
   9:  PR[99,3]=PR[99,3]+2.5    ;
  10:  IF (R[8:nSlot]=1) THEN ;
  11:  UFRAME_NUM=2 ;
  12:  UTOOL_NUM=3 ;
  13:J PR[99] 18% CNT62    ;
  14:  ELSE ;
  15:  IF (R[8:nSlot]=2) THEN ;
  16:  UFRAME_NUM=2 ;
  17:  UTOOL_NUM=3 ;
  18:C P[2]    
    :  P[3] 300mm/sec CNT71    ;
  19:  ELSE ;
  20:  UFRAME_NUM=2 ;
  21:  UTOOL_NUM=3 ;
  22:L PR[99] 300mm/sec FINE    ;
  23:  ENDIF ;
  24:  ENDIF ;
  25:  DO[3]=OFF ;
  26:  WAIT    .20(sec) ;
  27:  !TODO l.65 GOTO skip_log ;
  28:  MESSAGE[Placed in slot] ;
  29:  !TODO l.67 skip_log: ;
  30:  !TODO l.68 ERROR IF ERRNO=ERR_WAI ;
/POS
P[1]{
   GP1:
	UF : 2, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =   600.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 2, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =     0.000  mm,	Z =   500.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 2, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =   100.000  mm,	Z =   450.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
