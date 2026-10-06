/PROG  SETUP_FRAMES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm frames";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 14;
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
   1:  !CrossArm: tool and user frames ;
   2:  !of the ABB backup ;
   3:  !PR[100] is overwritten ;
   4:  MESSAGE[Overwrites UTOOL/UFRAME] ;
   5:  PAUSE ;
   6:  !UTOOL[1] tool0 ;
   7:  PR[100]=P[1]    ;
   8:  UTOOL[1]=PR[100] ;
   9:  !UTOOL[2] tMkTp ;
  10:  PR[100]=P[2]    ;
  11:  UTOOL[2]=PR[100] ;
  12:  !UFRAME[1] wMkTp ;
  13:  PR[100]=P[3]    ;
  14:  UFRAME[1]=PR[100] ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   150.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =     0.000  mm,	Z =   400.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
