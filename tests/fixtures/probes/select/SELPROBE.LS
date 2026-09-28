/PROG  SELPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SelProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 58;
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
   1:  !RAPID SelectProbe.SelProbe ;
   2:  R[1:nSum]=0    ;
   3:  R[2:nCalls]=0    ;
   4:  R[3:nPath]=0    ;
   5:  FOR R[4:i]=(-1) TO 4 ;
   6:  R[5:nMode]=R[4:i]    ;
   7:  SELECT R[5:nMode]=1,JMP LBL[4] ;
   8:         =2,JMP LBL[4] ;
   9:         =(-1),JMP LBL[5] ;
  10:         =3,CALL SELCOUNT ;
  11:         =4,JMP LBL[3] ;
  12:         ELSE,JMP LBL[6] ;
  13:  JMP LBL[3] ;
  14:  LBL[4] ;
  15:  R[1:nSum]=R[1:nSum]+10    ;
  16:  R[3:nPath]=R[3:nPath]+1    ;
  17:  SELECT R[5:nMode]=2,JMP LBL[2] ;
  18:  JMP LBL[1] ;
  19:  LBL[2] ;
  20:  R[3:nPath]=R[3:nPath]+10    ;
  21:  LBL[1] ;
  22:  JMP LBL[3] ;
  23:  LBL[5] ;
  24:  R[1:nSum]=R[1:nSum]+100    ;
  25:  JMP LBL[3] ;
  26:  LBL[6] ;
  27:  R[1:nSum]=R[1:nSum]+1000    ;
  28:  R[3:nPath]=R[3:nPath]+1    ;
  29:  LBL[3] ;
  30:  ENDFOR ;
  31:  R[5:nMode]=7    ;
  32:  SELECT R[5:nMode]=1,JMP LBL[8] ;
  33:         =7,CALL SELCOUNT ;
  34:  JMP LBL[7] ;
  35:  LBL[8] ;
  36:  R[1:nSum]=R[1:nSum]+5    ;
  37:  LBL[7] ;
  38:  R[5:nMode]=8    ;
  39:  SELECT R[5:nMode]=1,JMP LBL[10] ;
  40:  JMP LBL[9] ;
  41:  LBL[10] ;
  42:  R[1:nSum]=R[1:nSum]+5    ;
  43:  R[3:nPath]=R[3:nPath]+5    ;
  44:  LBL[9] ;
  45:  R[5:nMode]=2.5    ;
  46:  SELECT R[5:nMode]=2.5,JMP LBL[12] ;
  47:         ELSE,JMP LBL[13] ;
  48:  LBL[12] ;
  49:  R[1:nSum]=R[1:nSum]+20000    ;
  50:  R[3:nPath]=R[3:nPath]+1    ;
  51:  JMP LBL[11] ;
  52:  LBL[13] ;
  53:  R[1:nSum]=R[1:nSum]+50000    ;
  54:  LBL[11] ;
  55:  !l.55 TEST 2: one CASE ;
  56:  R[3:nPath]=R[3:nPath]+100    ;
  57:  CALL SELARG(3) ;
  58:  CALL SELARG(8) ;
/POS
/END
