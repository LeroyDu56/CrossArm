/PROG  THOLDB
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "tHoldB";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 18;
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
   1:  !RAPID StopProbe.tHoldB ;
   2:  CALL CA_STOPMOVE(1,1) ;
   3:  F[2]=(ON) ;
   4:  !l.55 ClearPath ;
   5:  R[2:nHolds]=R[2:nHolds]+1    ;
   6:  LBL[2] ;
   7:  IF (F[2]=OFF),JMP LBL[1] ;
   8:  F[3]=(DI[3]) ;
   9:  IF (F[3]=ON),JMP LBL[3] ;
  10:  WAIT DI[3]=ON    ;
  11:  JMP LBL[4] ;
  12:  LBL[3] ;
  13:  WAIT DI[3]=OFF    ;
  14:  LBL[4] ;
  15:  CALL TENABLE    ;
  16:  JMP LBL[2] ;
  17:  LBL[1] ;
  18:  MONITOR IHOLDB ;
/POS
/END
