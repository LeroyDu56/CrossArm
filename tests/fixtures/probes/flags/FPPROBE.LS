/PROG  FPPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FpProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 44;
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
   1:  !RAPID FlagProbe.FpProbe ;
   2:  R[1:fpN1]=0    ;
   3:  R[2:fpN2]=0    ;
   4:  R[3:fpN3]=0    ;
   5:  R[4:fpN4]=0    ;
   6:  R[5:fpN5]=0    ;
   7:  R[6:fpTurns]=0    ;
   8:  R[7:fpA]=3    ;
   9:  R[8:fpB]=7    ;
  10:  CALL CA_TEXT(1,'RUN',0) ;
  11:  F[1]=(R[7:fpA]<5) ;
  12:  F[2]=(R[7:fpA]<5 AND R[8:fpB]>8) ;
  13:  F[3]=(F[1]=OFF) ;
  14:  F[4]=(F[1]) ;
  15:  F[5]=(OFF) ;
  16:  CALL CA_TEXT(25,'RUN',0) ;
  17:  IF SR[1]<>SR[25],JMP LBL[1] ;
  18:  IF (R[7:fpA]<>3),JMP LBL[1] ;
  19:  F[5]=(ON) ;
  20:  LBL[1] ;
  21:  IF (F[1]=ON) THEN ;
  22:  R[1:fpN1]=1    ;
  23:  ENDIF ;
  24:  IF (F[2]=ON) THEN ;
  25:  R[2:fpN2]=1    ;
  26:  ENDIF ;
  27:  IF (F[3]=ON) THEN ;
  28:  R[3:fpN3]=1    ;
  29:  ENDIF ;
  30:  IF (F[4]=ON) THEN ;
  31:  R[4:fpN4]=1    ;
  32:  ENDIF ;
  33:  IF (F[5]=ON) THEN ;
  34:  R[5:fpN5]=1    ;
  35:  ENDIF ;
  36:  F[6]=(ON) ;
  37:  LBL[2] ;
  38:  IF (F[6]=OFF) THEN ;
  39:  JMP LBL[3] ;
  40:  ENDIF ;
  41:  R[6:fpTurns]=R[6:fpTurns]+1    ;
  42:  F[6]=(R[6:fpTurns]<4) ;
  43:  JMP LBL[2] ;
  44:  LBL[3] ;
/POS
/END
