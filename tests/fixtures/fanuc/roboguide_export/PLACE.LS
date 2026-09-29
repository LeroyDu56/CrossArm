/PROG  PLACE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Place           ";
PROG_SIZE	= 1141;
CREATE		= DATE 26-09-29  TIME 17:56:36;
MODIFIED	= DATE 26-09-29  TIME 17:56:36;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 28;
MEMORY_SIZE	= 1401;
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
   1:  !RAPID PickAndPlace.Place ;
   2:  PR[99]=P[1]    ;
   3:  R[4:NumberIndex]=R[2:nSlot]    ;
   4:  R[4:NumberIndex]=R[4:NumberIndex]+197    ;
   5:  PR[99,1]=PR[99,1]+R[R[4]]    ;
   6:  PR[99,3]=PR[99,3]+(-400)    ;
   7:  PR[99,3]=PR[99,3]+2.5    ;
   8:  IF (R[2:nSlot]=1) THEN ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=2 ;
  11:J PR[99] 40% CNT20    ;
  12:  ELSE ;
  13:  IF (R[2:nSlot]=2) THEN ;
  14:  UFRAME_NUM=1 ;
  15:  UTOOL_NUM=2 ;
  16:C P[2]    
    :  P[3] 300mm/sec CNT10    ;
  17:  ELSE ;
  18:  UFRAME_NUM=1 ;
  19:  UTOOL_NUM=2 ;
  20:L PR[99] 300mm/sec FINE    ;
  21:  ENDIF ;
  22:  ENDIF ;
  23:  DO[1]=OFF ;
  24:  WAIT    .20(sec) ;
  25:  !TODO l.65 GOTO skip_log ;
  26:  !TODO l.66 TPWrite 'Placed in slo ;
  27:  !TODO l.67 skip_log: ;
  28:  !TODO l.68 ERROR IF ERRNO=ERR_WAI ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   600.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =     0.000  mm,	Z =   500.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =   100.000  mm,	Z =   450.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
