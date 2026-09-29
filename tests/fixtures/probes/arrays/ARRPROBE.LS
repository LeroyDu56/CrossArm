/PROG  ARRPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ArrProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 38;
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
   1:  !RAPID ArrayProbe.ArrProbe ;
   2:  R[1:nSum]=0    ;
   3:  R[2:nCalls]=0    ;
   4:  R[3:nHits]=0    ;
   5:  FOR R[4:i]=1 TO 4 ;
   6:  R[5:NumberIndex]=R[4:i]    ;
   7:  R[5:NumberIndex]=R[5:NumberIndex]+196    ;
   8:  R[1:nSum]=R[1:nSum]+R[R[5]]    ;
   9:  IF (R[R[5]]<0) THEN ;
  10:  R[3:nHits]=R[3:nHits]+1    ;
  11:  ENDIF ;
  12:  ENDFOR ;
  13:  FOR R[6:r]=1 TO 2 ;
  14:  FOR R[7:c]=1 TO 3 ;
  15:  R[5:NumberIndex]=R[6:r]    ;
  16:  R[5:NumberIndex]=R[5:NumberIndex]*3    ;
  17:  R[5:NumberIndex]=R[5:NumberIndex]+R[7:c]    ;
  18:  R[5:NumberIndex]=R[5:NumberIndex]+187    ;
  19:  R[1:nSum]=R[1:nSum]+R[R[5]]    ;
  20:  R[8:NumberIndex2]=R[7:c]    ;
  21:  R[8:NumberIndex2]=R[8:NumberIndex2]+196    ;
  22:  CALL WEIGH(R[R[5]],R[R[8]]) ;
  23:  ENDFOR ;
  24:  ENDFOR ;
  25:  R[9:k]=1    ;
  26:  LBL[1] ;
  27:  R[5:NumberIndex]=R[9:k]    ;
  28:  R[5:NumberIndex]=R[5:NumberIndex]+187    ;
  29:  IF (R[R[5]]<=0) THEN ;
  30:  JMP LBL[2] ;
  31:  ENDIF ;
  32:  R[3:nHits]=R[3:nHits]+10    ;
  33:  R[9:k]=R[9:k]+1    ;
  34:  JMP LBL[1] ;
  35:  LBL[2] ;
  36:  R[5:NumberIndex]=R[9:k]    ;
  37:  R[5:NumberIndex]=R[5:NumberIndex]+187    ;
  38:  R[1:nSum]=R[1:nSum]+R[R[5]]    ;
/POS
/END
