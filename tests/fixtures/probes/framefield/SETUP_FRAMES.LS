/PROG  SETUP_FRAMES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm frames";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 43;
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
   3:  !CrossArm: tool and user frames ;
   4:  !of the ABB backup ;
   5:  !PR[100] is overwritten ;
   6:  MESSAGE[Overwrites UTOOL/UFRAME] ;
   7:  PAUSE ;
   8:  !UTOOL[1] tool0 ;
   9:  PR[100]=P[1]    ;
  10:  UTOOL[1]=PR[100] ;
  11:  !UTOOL[2] ffStylus ;
  12:  PR[100]=P[2]    ;
  13:  UTOOL[2]=PR[100] ;
  14:  !UFRAME[1] ffPallet ;
  15:  PR[100]=P[3]    ;
  16:  UFRAME[1]=PR[100] ;
  17:  !UFRAME[2] ffNest1 ;
  18:  PR[100]=P[4]    ;
  19:  UFRAME[2]=PR[100] ;
  20:  !UFRAME[3] ffNest8 ;
  21:  PR[100]=P[5]    ;
  22:  UFRAME[3]=PR[100] ;
  23:  !UFRAME[4] ffNest9 ;
  24:  PR[100]=P[6]    ;
  25:  UFRAME[4]=PR[100] ;
  26:  !UFRAME[5] ffNest2 ;
  27:  PR[100]=P[7]    ;
  28:  UFRAME[5]=PR[100] ;
  29:  !UFRAME[6] ffNest3 ;
  30:  PR[100]=P[8]    ;
  31:  UFRAME[6]=PR[100] ;
  32:  !UFRAME[7] ffNest4 ;
  33:  PR[100]=P[9]    ;
  34:  UFRAME[7]=PR[100] ;
  35:  !UFRAME[8] ffNest5 ;
  36:  PR[100]=P[10]    ;
  37:  UFRAME[8]=PR[100] ;
  38:  !ffNest6: PR[99], UFRAME[9] when ;
  39:  !used ;
  40:  PR[99]=P[11]    ;
  41:  !ffNest7: PR[98], UFRAME[9] when ;
  42:  !used ;
  43:  PR[98]=P[12]    ;
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
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   970.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =    20.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   150.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[12]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
