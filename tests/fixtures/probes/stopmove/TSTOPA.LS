/PROG  TSTOPA
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "tStopA";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 15;
MEMORY_SIZE	= 0;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 2;
DEFAULT_GROUP	= *,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID StopProbe.tStopA ;
   2:  LBL[1] ;
   3:  F[1]=(DI[1]) ;
   4:  CALL CA_STOPMOVE(1,1) ;
   5:  F[2]=(ON) ;
   6:  R[1:nPaused]=R[1:nPaused]+1    ;
   7:  CALL STOPWAIT    ;
   8:  IF (F[2]=OFF),JMP LBL[2] ;
   9:  IF (F[1]=OFF),JMP LBL[3] ;
  10:  WAIT DI[1]=OFF    ;
  11:  LBL[3] ;
  12:  WAIT DI[1]=ON    ;
  13:  JMP LBL[1] ;
  14:  LBL[2] ;
  15:  MONITOR ISTOPA ;
/POS
/END
