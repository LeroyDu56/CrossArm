/PROG  SETUP_FRAMES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm frames";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 52;
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
   8:  !UTOOL[1] fiT1 ;
   9:  PR[100]=P[1]    ;
  10:  UTOOL[1]=PR[100] ;
  11:  !UTOOL[2] tool0 ;
  12:  PR[100]=P[2]    ;
  13:  UTOOL[2]=PR[100] ;
  14:  !UTOOL[3] fiT2 ;
  15:  PR[100]=P[3]    ;
  16:  UTOOL[3]=PR[100] ;
  17:  !UTOOL[4] fiT3 ;
  18:  PR[100]=P[4]    ;
  19:  UTOOL[4]=PR[100] ;
  20:  !UTOOL[5] fiT4 ;
  21:  PR[100]=P[5]    ;
  22:  UTOOL[5]=PR[100] ;
  23:  !UTOOL[6] fiHeavy ;
  24:  PR[100]=P[6]    ;
  25:  UTOOL[6]=PR[100] ;
  26:  !UTOOL[7] fiShift ;
  27:  PR[100]=P[7]    ;
  28:  UTOOL[7]=PR[100] ;
  29:  !UTOOL[8] fiT5 ;
  30:  PR[100]=P[8]    ;
  31:  UTOOL[8]=PR[100] ;
  32:  !UTOOL[9] fiT6 ;
  33:  PR[100]=P[9]    ;
  34:  UTOOL[9]=PR[100] ;
  35:  !fiTurn: PR[99], UTOOL[10] when ;
  36:  !used ;
  37:  PR[99]=P[10]    ;
  38:  !fiGrip: PR[98], UTOOL[10] when ;
  39:  !used ;
  40:  PR[98]=P[11]    ;
  41:  !fiCam: PR[97], UTOOL[10] when ;
  42:  !used ;
  43:  PR[97]=P[12]    ;
  44:  !UFRAME[1] fiLeft ;
  45:  PR[100]=P[13]    ;
  46:  UFRAME[1]=PR[100] ;
  47:  !UFRAME[2] fiRight ;
  48:  PR[100]=P[14]    ;
  49:  UFRAME[2]=PR[100] ;
  50:  !UFRAME[3] fiTable ;
  51:  PR[100]=P[15]    ;
  52:  UFRAME[3]=PR[100] ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   100.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[12]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =     0.000  mm,	Z =    90.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[13]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[14]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
