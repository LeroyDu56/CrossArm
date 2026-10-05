/PROG  FAPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FaProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 57;
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
   1:  !RAPID FlagArrayProbe.FaProbe ;
   2:  R[4:faCount]=0    ;
   3:  R[5:faPairs]=0    ;
   4:  R[6:faFixed]=0    ;
   5:  R[7:faFirst]=0    ;
   6:  FOR R[8:i]=1 TO 2 ;
   7:  FOR R[9:j]=1 TO 3 ;
   8:  R[2:NumberIndex]=R[8:i]    ;
   9:  R[2:NumberIndex]=R[2:NumberIndex]*3    ;
  10:  R[2:NumberIndex]=R[2:NumberIndex]+R[9:j]    ;
  11:  R[2:NumberIndex]=R[2:NumberIndex]+1009    ;
  12:  F[R[2]]=(OFF) ;
  13:  ENDFOR ;
  14:  ENDFOR ;
  15:  CALL FAMARK    ;
  16:  F[1019]=(ON) ;
  17:  F[1020]=(F[1023]=ON AND F[1021]=OFF) ;
  18:  CALL FATALLY    ;
  19:  R[10:faK]=2    ;
  20:  R[11:Calc8]=R[10:faK]+1    ;
  21:  R[2:NumberIndex]=R[10:faK]    ;
  22:  R[2:NumberIndex]=R[2:NumberIndex]*3    ;
  23:  R[2:NumberIndex]=R[2:NumberIndex]+R[11:Calc8]    ;
  24:  R[2:NumberIndex]=R[2:NumberIndex]+1009    ;
  25:  F[R[2]]=(ON) ;
  26:  R[11:Calc8]=R[10:faK]+1    ;
  27:  R[2:NumberIndex]=R[11:Calc8]    ;
  28:  R[2:NumberIndex]=R[2:NumberIndex]+1018    ;
  29:  R[12:NumberIndex2]=1    ;
  30:  R[12:NumberIndex2]=R[12:NumberIndex2]*3    ;
  31:  R[12:NumberIndex2]=R[12:NumberIndex2]+R[10:faK]    ;
  32:  R[12:NumberIndex2]=R[12:NumberIndex2]+1009    ;
  33:  F[R[12]]=(F[R[2]]) ;
  34:  F[1013]=(F[1018]=OFF) ;
  35:  R[11:Calc8]=R[10:faK]*3    ;
  36:  R[2:NumberIndex]=R[11:Calc8]    ;
  37:  R[2:NumberIndex]=R[2:NumberIndex]+1018    ;
  38:  F[1016]=(F[R[2]]) ;
  39:  FOR R[8:i]=1 TO 2 ;
  40:  FOR R[9:j]=1 TO 3 ;
  41:  R[2:NumberIndex]=R[8:i]    ;
  42:  R[2:NumberIndex]=R[2:NumberIndex]*3    ;
  43:  R[2:NumberIndex]=R[2:NumberIndex]+R[9:j]    ;
  44:  R[2:NumberIndex]=R[2:NumberIndex]+1009    ;
  45:  IF (F[R[2]]=ON) THEN ;
  46:  R[14:Calc2]=R[8:i]*10    ;
  47:  R[13:Calc1]=R[5:faPairs]+R[14:Calc2]    ;
  48:  R[5:faPairs]=R[13:Calc1]+R[9:j]    ;
  49:  ENDIF ;
  50:  ENDFOR ;
  51:  ENDFOR ;
  52:  IF (F[1020]=ON AND F[1018]=ON) THEN ;
  53:  R[6:faFixed]=1    ;
  54:  ENDIF ;
  55:  IF (F[1021]=OFF) THEN ;
  56:  R[7:faFirst]=1    ;
  57:  ENDIF ;
/POS
/END
