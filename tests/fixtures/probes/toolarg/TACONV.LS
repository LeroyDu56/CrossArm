/PROG  TACONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "TaConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 63;
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
   3:  !RAPID ToolArgProbe.TaConv ;
   4:  R[1:taDone]=0    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 11% FINE    ;
   8:  PR[99]=LPOS    ;
   9:  R[2:taLen]=PR[99,3]-650    ;
  10:  CALL TALENGTH(2,R[2:taLen]) ;
  11:  R[3:Calc1]=R[2:taLen]+30    ;
  12:  CALL TALENGTH(3,R[3:Calc1]) ;
  13:  UFRAME_NUM=0 ;
  14:  UTOOL_NUM=2 ;
  15:L P[2] 500mm/sec FINE    ;
  16:  UTOOL_NUM=1 ;
  17:  PR[98]=LPOS    ;
  18:  UTOOL_NUM=3 ;
  19:L P[3] 500mm/sec FINE    ;
  20:  UTOOL_NUM=1 ;
  21:  PR[97]=LPOS    ;
  22:  F[1]=(OFF) ;
  23:  IF (F[1]=ON) THEN ;
  24:  R[4:bOk]=1    ;
  25:  ELSE ;
  26:  R[4:bOk]=0    ;
  27:  ENDIF ;
  28:  PR[96]=P[4]    ;
  29:  CALL TACHECK(R[2:taLen],R[4:bOk],1) ;
  30:  F[1]=(R[4:bOk]=1) ;
  31:  UFRAME_NUM=0 ;
  32:  UTOOL_NUM=1 ;
  33:  PR[95]=LPOS    ;
  34:  IF (F[1]=ON) THEN ;
  35:  R[5:taOk1]=1    ;
  36:  ELSE ;
  37:  R[5:taOk1]=2    ;
  38:  ENDIF ;
  39:  R[3:Calc1]=R[2:taLen]+1000    ;
  40:  IF (F[1]=ON) THEN ;
  41:  R[4:bOk]=1    ;
  42:  ELSE ;
  43:  R[4:bOk]=0    ;
  44:  ENDIF ;
  45:  CALL TACHECK(R[3:Calc1],R[4:bOk],0) ;
  46:  F[1]=(R[4:bOk]=1) ;
  47:  IF (F[1]=ON) THEN ;
  48:  R[6:taOk2]=1    ;
  49:  ELSE ;
  50:  R[6:taOk2]=2    ;
  51:  ENDIF ;
  52:  PR[94]=PR[95]    ;
  53:  PR[94,1]=PR[98,1]    ;
  54:  PR[94,2]=PR[98,2]    ;
  55:  PR[94,3]=PR[98,3]    ;
  56:  PR[94,4]=PR[97,4]    ;
  57:  PR[94,5]=PR[97,5]    ;
  58:  PR[94,6]=PR[97,6]    ;
  59:  UFRAME_NUM=0 ;
  60:  UTOOL_NUM=1 ;
  61:L PR[94] 500mm/sec FINE    ;
  62:  PR[93]=LPOS    ;
  63:  R[1:taDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1050.000  mm,	Y =    80.000  mm,	Z =   760.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -155.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =  1050.000  mm,	Y =    80.000  mm,	Z =   760.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -155.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   980.000  mm,	Y =   -90.000  mm,	Z =   840.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
