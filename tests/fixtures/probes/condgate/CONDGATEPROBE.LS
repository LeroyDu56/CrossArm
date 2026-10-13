/PROG  CONDGATEPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CondGateProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 64;
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
   1:  !RAPID ;
   2:  !CondGateProbe.CondGateProbe ;
   3:  R[1:nBefore]=1    ;
   4:  CALL CA_TEXT(1,'A',0) ;
   5:  !TODO l.15 IF OpMode()=OP_AUTO TH ;
   6:  !Replace JMP by F[1]=(...) ;
   7:  JMP LBL[1] ;
   8:  IF (F[1]=ON) THEN ;
   9:  R[2:nThen]=R[2:nThen]+1    ;
  10:  ELSE ;
  11:  R[3:nElse]=R[3:nElse]+1    ;
  12:  ENDIF ;
  13:  LBL[1] ;
  14:  !TODO l.22 ELSEIF OpMode()=OP_AUT ;
  15:  !Replace JMP by F[2]=(...) ;
  16:  JMP LBL[2] ;
  17:  IF (R[1:nBefore]>5) THEN ;
  18:  R[2:nThen]=R[2:nThen]+10    ;
  19:  ELSE ;
  20:  IF (F[2]=ON) THEN ;
  21:  R[4:nElseIf]=R[4:nElseIf]+1    ;
  22:  ELSE ;
  23:  R[3:nElse]=R[3:nElse]+10    ;
  24:  ENDIF ;
  25:  ENDIF ;
  26:  LBL[2] ;
  27:  !TODO l.29 ELSEIF OpMode()=OP_AUT ;
  28:  !Replace JMP by F[1024]=(...) ;
  29:  JMP LBL[6] ;
  30:  CALL CA_TEXT(25,'B',0) ;
  31:  IF SR[1]<>SR[25],JMP LBL[4] ;
  32:  R[2:nThen]=R[2:nThen]+100    ;
  33:  JMP LBL[3] ;
  34:  LBL[4] ;
  35:  IF (F[1024]=OFF),JMP LBL[5] ;
  36:  R[4:nElseIf]=R[4:nElseIf]+10    ;
  37:  JMP LBL[3] ;
  38:  LBL[5] ;
  39:  R[3:nElse]=R[3:nElse]+100    ;
  40:  LBL[3] ;
  41:  LBL[6] ;
  42:  LBL[7] ;
  43:  !TODO l.34 WHILE OpMode()<>OP_AUT ;
  44:  !Replace JMP by F[3]=(...) ;
  45:  JMP LBL[8] ;
  46:  IF (F[3]=OFF) THEN ;
  47:  JMP LBL[8] ;
  48:  ENDIF ;
  49:  R[5:nLoops]=R[5:nLoops]+1    ;
  50:  JMP LBL[7] ;
  51:  LBL[8] ;
  52:  !TODO l.37 TEST StrLen(sMode) ;
  53:  !Replace JMP by R[200]=(...) ;
  54:  JMP LBL[12] ;
  55:  SELECT R[200]=1,JMP LBL[10] ;
  56:         ELSE,JMP LBL[11] ;
  57:  LBL[10] ;
  58:  R[199:nCase]=1    ;
  59:  JMP LBL[9] ;
  60:  LBL[11] ;
  61:  R[199:nCase]=2    ;
  62:  LBL[9] ;
  63:  LBL[12] ;
  64:  R[6:nAfter]=1    ;
/POS
/END
