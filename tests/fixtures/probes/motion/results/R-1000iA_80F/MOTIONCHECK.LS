/PROG  MOTIONCHECK
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "motion check";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 112;
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
   1:  !CrossArm motion check ;
   2:  PR[20]=P[10]    ;
   3:  UTOOL[1]=PR[20] ;
   4:  !RAPID MotionCheck.CheckPath ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 29% FINE    ;
   8:  TIMER[1]=RESET ;
   9:  TIMER[1]=START ;
  10:J P[2] 12% FINE    ;
  11:  TIMER[1]=STOP ;
  12:  R[101]=TIMER[1]    ;
  13:J P[1] 29% FINE    ;
  14:  TIMER[1]=RESET ;
  15:  TIMER[1]=START ;
  16:J P[2] 18% FINE    ;
  17:  TIMER[1]=STOP ;
  18:  R[102]=TIMER[1]    ;
  19:J P[3] 29% FINE    ;
  20:  TIMER[1]=RESET ;
  21:  TIMER[1]=START ;
  22:J P[4] 12% FINE    ;
  23:  TIMER[1]=STOP ;
  24:  R[103]=TIMER[1]    ;
  25:J P[3] 29% FINE    ;
  26:  TIMER[1]=RESET ;
  27:  TIMER[1]=START ;
  28:J P[4] 18% FINE    ;
  29:  TIMER[1]=STOP ;
  30:  R[104]=TIMER[1]    ;
  31:J P[5] 29% FINE    ;
  32:  TIMER[1]=RESET ;
  33:  TIMER[1]=START ;
  34:J P[6] 12% FINE    ;
  35:  TIMER[1]=STOP ;
  36:  R[105]=TIMER[1]    ;
  37:J P[5] 29% FINE    ;
  38:  TIMER[1]=RESET ;
  39:  TIMER[1]=START ;
  40:J P[6] 18% FINE    ;
  41:  TIMER[1]=STOP ;
  42:  R[106]=TIMER[1]    ;
  43:J P[7] 29% FINE    ;
  44:  TIMER[1]=RESET ;
  45:  TIMER[1]=START ;
  46:L P[8] 300mm/sec CNT55    ;
  47:L P[9] 300mm/sec FINE    ;
  48:  TIMER[1]=STOP ;
  49:  R[107]=TIMER[1]    ;
  50:J P[7] 29% FINE    ;
  51:  TIMER[1]=RESET ;
  52:  TIMER[1]=START ;
  53:L P[8] 300mm/sec CNT69    ;
  54:L P[9] 300mm/sec FINE    ;
  55:  TIMER[1]=STOP ;
  56:  R[108]=TIMER[1]    ;
  57:J P[7] 29% FINE    ;
  58:  TIMER[1]=RESET ;
  59:  TIMER[1]=START ;
  60:L P[8] 300mm/sec CNT100    ;
  61:L P[9] 300mm/sec FINE    ;
  62:  TIMER[1]=STOP ;
  63:  R[109]=TIMER[1]    ;
  64:J P[7] 29% FINE    ;
  65:  TIMER[1]=RESET ;
  66:  TIMER[1]=START ;
  67:L P[8] 300mm/sec CNT100    ;
  68:L P[9] 300mm/sec FINE    ;
  69:  TIMER[1]=STOP ;
  70:  R[110]=TIMER[1]    ;
  71:J P[7] 29% FINE    ;
  72:  TIMER[1]=RESET ;
  73:  TIMER[1]=START ;
  74:L P[8] 600mm/sec CNT32    ;
  75:L P[9] 600mm/sec FINE    ;
  76:  TIMER[1]=STOP ;
  77:  R[111]=TIMER[1]    ;
  78:J P[7] 29% FINE    ;
  79:  TIMER[1]=RESET ;
  80:  TIMER[1]=START ;
  81:L P[8] 600mm/sec CNT41    ;
  82:L P[9] 600mm/sec FINE    ;
  83:  TIMER[1]=STOP ;
  84:  R[112]=TIMER[1]    ;
  85:J P[7] 29% FINE    ;
  86:  TIMER[1]=RESET ;
  87:  TIMER[1]=START ;
  88:L P[8] 600mm/sec CNT57    ;
  89:L P[9] 600mm/sec FINE    ;
  90:  TIMER[1]=STOP ;
  91:  R[113]=TIMER[1]    ;
  92:J P[7] 29% FINE    ;
  93:  TIMER[1]=RESET ;
  94:  TIMER[1]=START ;
  95:L P[8] 600mm/sec CNT71    ;
  96:L P[9] 600mm/sec FINE    ;
  97:  TIMER[1]=STOP ;
  98:  R[114]=TIMER[1]    ;
  99:J P[7] 29% FINE    ;
 100:  TIMER[1]=RESET ;
 101:  TIMER[1]=START ;
 102:J P[8] 18% CNT41    ;
 103:J P[9] 18% FINE    ;
 104:  TIMER[1]=STOP ;
 105:  R[115]=TIMER[1]    ;
 106:J P[7] 29% FINE    ;
 107:  TIMER[1]=RESET ;
 108:  TIMER[1]=START ;
 109:J P[8] 18% CNT55    ;
 110:J P[9] 18% FINE    ;
 111:  TIMER[1]=STOP ;
 112:  R[116]=TIMER[1]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -400.000  mm,	Z =   600.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1400.000  mm,	Y =   300.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -500.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   500.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =     0.000  mm,	Z =   500.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =     0.000  mm,	Z =  1100.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -200.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1400.000  mm,	Y =  -200.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1400.000  mm,	Y =   200.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
