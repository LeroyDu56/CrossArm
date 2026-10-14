/PROG  TENABLE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "tEnable";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 21;
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
   1:  !RAPID StopProbe.tEnable ;
   2:  LBL[1] ;
   3:  F[3]=(DI[3]) ;
   4:  R[3:nEnables]=R[3:nEnables]+1    ;
   5:  IF (DI[3]=ON) THEN ;
   6:  CALL CA_STOPMOVE(0,1) ;
   7:  F[2]=(OFF) ;
   8:  ELSE ;
   9:  CALL CA_STOPMOVE(1,1) ;
  10:  F[2]=(ON) ;
  11:  ENDIF ;
  12:  IF (F[2]=OFF),JMP LBL[2] ;
  13:  IF (F[3]=ON),JMP LBL[3] ;
  14:  WAIT DI[3]=ON    ;
  15:  JMP LBL[4] ;
  16:  LBL[3] ;
  17:  WAIT DI[3]=OFF    ;
  18:  LBL[4] ;
  19:  JMP LBL[1] ;
  20:  LBL[2] ;
  21:  MONITOR IENABLE ;
/POS
/END
