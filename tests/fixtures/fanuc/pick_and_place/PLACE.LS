/PROG  PLACE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Place";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 08:00:00;
MODIFIED	= DATE 26-01-01  TIME 08:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 20;
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
   1:  !RAPID PickAndPlace.Place ;
   2:  !TODO l.54 pPlace:=Offs(pHome,nOf ;
   3:  !TODO l.55 pPlace.trans.z:=pPlace ;
   4:  IF (R[2:nSlot]=1) THEN ;
   5:  !TODO l.57 MoveJ pPlace,v800,z20, ;
   6:  ELSE ;
   7:  IF (R[2:nSlot]=2) THEN ;
   8:  UFRAME_NUM=1 ;
   9:  UTOOL_NUM=2 ;
  10:C P[1]    
    :  P[2] 300mm/sec CNT71    ;
  11:  ELSE ;
  12:  !TODO l.61 MoveL pPlace,v300,fine ;
  13:  ENDIF ;
  14:  ENDIF ;
  15:  DO[1]=OFF ;
  16:  WAIT    .20(sec) ;
  17:  !TODO l.65 GOTO skip_log ;
  18:  MESSAGE[Placed in slot] ;
  19:  !TODO l.67 skip_log: ;
  20:  !TODO l.68 ERROR IF ERRNO=ERR_WAI ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =     0.000  mm,	Z =   500.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =   100.000  mm,	Z =   450.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
