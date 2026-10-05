/PROG  PICK
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Pick";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 11;
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
   3:  !RAPID PickAndPlace.Pick ;
   4:  ! approach, grip, retract ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=3 ;
   7:J P[1] 22% CNT55    ;
   8:L P[2] 200mm/sec FINE    ;
   9:  DO[3]=ON ;
  10:  WAIT    .30(sec) ;
  11:L P[1] 500mm/sec CNT54    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 3,		CONFIG : 'N U T, 0, 0, 1',
	X =   812.350  mm,	Y =  -245.100  mm,	Z =   405.000  mm,
	W =  -179.293 deg,	P =     0.000 deg,	R =   -90.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 3,		CONFIG : 'N U T, 0, 0, 1',
	X =   812.350  mm,	Y =  -245.100  mm,	Z =   305.000  mm,
	W =  -179.293 deg,	P =     0.000 deg,	R =   -90.000 deg
};
/END
