/PROG  RECCOUNT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RecCount";
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
   1:  !RAPID RecordProbe.RecCount ;
   2:  R[3:RECCOUNT.tallyNo]=0    ;
   3:  IF (R[3:RECCOUNT.tallyNo]<>0) THEN ;
   4:  R[4:nBad]=R[4:nBad]+1    ;
   5:  ENDIF ;
   6:  IF (F[1]=ON) THEN ;
   7:  R[5:nBusy]=R[5:nBusy]+1    ;
   8:  ENDIF ;
   9:  IF (F[1]=ON) THEN ;
  10:  F[2]=(ON) ;
  11:  ENDIF ;
  12:  R[3:RECCOUNT.tallyNo]=R[6:nSteps]+1    ;
  13:  R[6:nSteps]=R[3:RECCOUNT.tallyNo]    ;
  14:  R[7:tallyLast.n]=R[6:nSteps]    ;
/POS
/END
