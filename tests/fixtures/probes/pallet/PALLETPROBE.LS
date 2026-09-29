/PROG  PALLETPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PalletProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 68;
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
   1:  !RAPID PalletProbe.PalletProbe ;
   2:  FOR R[1:k]=1 TO 2 ;
   3:  FOR R[2:c]=1 TO 2 ;
   4:  PR[99]=P[1]    ;
   5:  R[3:Calc1]=R[2:c]-1    ;
   6:  R[3:Calc1]=R[3:Calc1]*90    ;
   7:  R[4:NumberIndex]=R[1:k]    ;
   8:  R[4:NumberIndex]=R[4:NumberIndex]+198    ;
   9:  R[3:Calc1]=R[3:Calc1]+R[R[4]]    ;
  10:  PR[99,1]=PR[99,1]+R[3:Calc1]    ;
  11:  R[3:Calc1]=R[1:k]-1    ;
  12:  R[3:Calc1]=R[3:Calc1]*20    ;
  13:  PR[99,2]=PR[99,2]+R[3:Calc1]    ;
  14:  R[3:Calc1]=R[1:k]-1    ;
  15:  R[3:Calc1]=R[3:Calc1]*25    ;
  16:  PR[99,3]=PR[99,3]+R[3:Calc1]    ;
  17:  IF (R[1:k]=2) THEN ;
  18:  PR[99,4]=180    ;
  19:  PR[99,5]=0    ;
  20:  PR[99,6]=(-90)    ;
  21:  ENDIF ;
  22:  PR[98]=PR[99]    ;
  23:  PR[98,3]=PR[98,3]+40    ;
  24:  UFRAME_NUM=1 ;
  25:  UTOOL_NUM=1 ;
  26:L PR[98] 500mm/sec FINE    ;
  27:  UFRAME_NUM=0 ;
  28:  UTOOL_NUM=9 ;
  29:  PR[R[90]]=LPOS    ;
  30:  R[90]=R[90]+1    ;
  31:  UFRAME_NUM=1 ;
  32:  UTOOL_NUM=1 ;
  33:L PR[99] 200mm/sec FINE    ;
  34:  UFRAME_NUM=0 ;
  35:  UTOOL_NUM=9 ;
  36:  PR[R[90]]=LPOS    ;
  37:  R[90]=R[90]+1    ;
  38:  UFRAME_NUM=1 ;
  39:  UTOOL_NUM=1 ;
  40:  PR[98]=P[1]    ;
  41:  R[3:Calc1]=R[2:c]*90    ;
  42:  PR[98,1]=PR[98,1]+R[3:Calc1]    ;
  43:  R[3:Calc1]=R[1:k]*20    ;
  44:  PR[98,2]=PR[98,2]+R[3:Calc1]    ;
  45:  PR[98,3]=PR[98,3]+60    ;
  46:L PR[98] 500mm/sec FINE    ;
  47:  UFRAME_NUM=0 ;
  48:  UTOOL_NUM=9 ;
  49:  PR[R[90]]=LPOS    ;
  50:  R[90]=R[90]+1    ;
  51:  UFRAME_NUM=1 ;
  52:  UTOOL_NUM=1 ;
  53:  ENDFOR ;
  54:  ENDFOR ;
  55:  UFRAME_NUM=1 ;
  56:  UTOOL_NUM=1 ;
  57:  PR[97]=LPOS    ;
  58:  PR[97,1]=PR[97,1]+15    ;
  59:  PR[98]=PR[97]    ;
  60:  PR[98,2]=PR[98,2]+10    ;
  61:  PR[98,3]=PR[98,3]+30    ;
  62:L PR[98] 200mm/sec FINE    ;
  63:  UFRAME_NUM=0 ;
  64:  UTOOL_NUM=9 ;
  65:  PR[R[90]]=LPOS    ;
  66:  R[90]=R[90]+1    ;
  67:  UFRAME_NUM=1 ;
  68:  UTOOL_NUM=1 ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
