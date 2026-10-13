/PROG  FORBOUNDSET
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ForBoundProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 62;
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
   2:  !ForBoundProbe.ForBoundProbe ;
   3:  R[1:nBefore]=1    ;
   4:  R[2:nCount]=4    ;
   5:  R[3:nTwo]=2    ;
   6:  FOR R[4:i]=1 TO R[2:nCount] ;
   7:  R[5:nTo]=R[5:nTo]+1    ;
   8:  ENDFOR ;
   9:  FOR R[4:i]=R[2:nCount] DOWNTO 2 ;
  10:  R[6:nDown]=R[6:nDown]+1    ;
  11:  ENDFOR ;
  12:  R[7:Calc1]=R[2:nCount]*2    ;
  13:  R[8:FOR TO l.33]=R[7:Calc1]-3    ;
  14:  FOR R[4:i]=2 TO R[8:FOR TO l.33] ;
  15:  R[9:nCalc]=R[9:nCalc]+1    ;
  16:  ENDFOR ;
  17:  R[10:FOR TO l.36]=R[3:nTwo]+1    ;
  18:  FOR R[4:i]=1 TO R[10:FOR TO l.36] ;
  19:  R[12:FOR FROM l.37]=R[3:nTwo]-1    ;
  20:  FOR R[11:j]=R[12:FOR FROM l.37] TO R[3:nTwo] ;
  21:  R[13:nNest]=R[13:nNest]+1    ;
  22:  ENDFOR ;
  23:  ENDFOR ;
  24:  R[14:FOR TO l.41]=R[2:nCount]    ;
  25:  FOR R[4:i]=1 TO R[14:FOR TO l.41] ;
  26:  R[2:nCount]=R[2:nCount]-1    ;
  27:  R[15:nShrink]=R[15:nShrink]+1    ;
  28:  ENDFOR ;
  29:  R[16:FOR TO l.45]=R[3:nTwo]-1    ;
  30:  FOR R[4:i]=R[3:nTwo] TO R[16:FOR TO l.45] ;
  31:  R[17:nNone]=R[17:nNone]+1    ;
  32:  ENDFOR ;
  33:  R[4:i]=0    ;
  34:  LBL[1] ;
  35:  IF R[4:i]>20,JMP LBL[2] ;
  36:  R[18:nStepSum]=R[18:nStepSum]+R[4:i]    ;
  37:  R[4:i]=R[4:i]+4    ;
  38:  JMP LBL[1] ;
  39:  LBL[2] ;
  40:  R[19:FOR FROM l.51]=R[3:nTwo]*5    ;
  41:  R[4:i]=R[19:FOR FROM l.51]    ;
  42:  LBL[3] ;
  43:  IF R[4:i]<R[3:nTwo],JMP LBL[4] ;
  44:  R[20:nStepDown]=R[20:nStepDown]+1    ;
  45:  R[4:i]=R[4:i]-3    ;
  46:  JMP LBL[3] ;
  47:  LBL[4] ;
  48:  R[4:i]=0    ;
  49:  LBL[5] ;
  50:  IF R[4:i]>1,JMP LBL[6] ;
  51:  R[21:nQuarter]=R[21:nQuarter]+1    ;
  52:  R[4:i]=R[4:i]+.25    ;
  53:  JMP LBL[5] ;
  54:  LBL[6] ;
  55:  !TODO l.57 FOR i FROM 1 TO CycleC ;
  56:  !Replace JMP by R[22]=(...) ;
  57:  R[22]=3 ;
  58:  FOR R[4:i]=1 TO R[22] ;
  59:  R[23:nGated]=R[23:nGated]+1    ;
  60:  ENDFOR ;
  61:  LBL[7] ;
  62:  R[24:nAfter]=1    ;
/POS
/END
