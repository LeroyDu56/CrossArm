/PROG  FBPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FbProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 67;
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
   3:  !RAPID FuncBodyProbe.FbProbe ;
   4:  R[1:fbDone]=0    ;
   5:  R[2:fbSum]=0    ;
   6:  R[3:fbFlags]=0    ;
   7:  R[4:fbLoops]=0    ;
   8:  R[5:fbCount]=0    ;
   9:  R[6:fbBack]=0    ;
  10:  R[7:fbBias]=.5    ;
  11:  FOR R[8:i]=1 TO 4 ;
  12:  CALL FBSCALE(R[8:i],9) ;
  13:  R[10:Calc2]=R[9:result]*10    ;
  14:  R[2:fbSum]=R[2:fbSum]+R[10:Calc2]    ;
  15:  CALL FBEVEN(R[8:i],11) ;
  16:  IF (R[11:result]=1) THEN ;
  17:  R[3:fbFlags]=R[3:fbFlags]+1    ;
  18:  ELSE ;
  19:  CALL FBBIG(R[8:i],12) ;
  20:  IF (R[12:result]=1) THEN ;
  21:  R[3:fbFlags]=R[3:fbFlags]+100    ;
  22:  ENDIF ;
  23:  ENDIF ;
  24:  ENDFOR ;
  25:  LBL[1] ;
  26:  CALL FBDONE(13) ;
  27:  IF (R[13:result]=1) THEN ;
  28:  JMP LBL[2] ;
  29:  ENDIF ;
  30:  R[4:fbLoops]=R[4:fbLoops]+1    ;
  31:  JMP LBL[1] ;
  32:  LBL[2] ;
  33:  CALL FBSCALE(R[4:fbLoops],9) ;
  34:  CALL FBOUTER(3,15) ;
  35:  R[14:fbNest]=R[9:result]+R[15:result]    ;
  36:  CALL FBCELL(R[4:fbLoops],3,98) ;
  37:  PR[99]=PR[98]    ;
  38:  UFRAME_NUM=0 ;
  39:  UTOOL_NUM=1 ;
  40:J PR[99] 11% FINE    ;
  41:  R[16:fbX]=PR[99,1]    ;
  42:  R[17:fbY]=PR[99,2]    ;
  43:  R[18:fbZ]=PR[99,3]    ;
  44:  CALL FBCELL(1,1,98) ;
  45:  UFRAME_NUM=0 ;
  46:  UTOOL_NUM=1 ;
  47:L PR[98] 500mm/sec FINE    ;
  48:  PR[97]=LPOS    ;
  49:  R[19:fbX1]=PR[97,1]    ;
  50:  R[20:fbY1]=PR[97,2]    ;
  51:  CALL FBBIG(1,12) ;
  52:  F[1]=(R[12:result]=1) ;
  53:  IF (F[1]=ON) THEN ;
  54:  R[6:fbBack]=1    ;
  55:  ELSE ;
  56:  R[6:fbBack]=2    ;
  57:  ENDIF ;
  58:  CALL FBEVEN(2,11) ;
  59:  IF (R[11:result]=0) THEN ;
  60:  R[6:fbBack]=R[6:fbBack]+10    ;
  61:  ENDIF ;
  62:  R[21:Calc1]=R[6:fbBack]+1    ;
  63:  CALL FBEVEN(R[21:Calc1],11) ;
  64:  IF (R[11:result]=0) THEN ;
  65:  R[6:fbBack]=R[6:fbBack]+100    ;
  66:  ENDIF ;
  67:  R[1:fbDone]=1    ;
/POS
/END
