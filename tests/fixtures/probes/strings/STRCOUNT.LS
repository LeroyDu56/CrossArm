/PROG  STRCOUNT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "StrCount";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 35;
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
   1:  !RAPID StringProbe.StrCount ;
   2:  R[1:i]=1    ;
   3:  CALL CA_TEXT(1,'x',0) ;
   4:  SR[1]=SUBSTR SR[1],2,0 ;
   5:  LBL[1] ;
   6:  R[200:Calc2]=STRLEN SR[2]    ;
   7:  IF (R[1:i]>R[200:Calc2]) THEN ;
   8:  JMP LBL[2] ;
   9:  ENDIF ;
  10:  SR[1]=SUBSTR SR[2],R[1:i],1 ;
  11:  CALL CA_TEXT(25,'A',0) ;
  12:  IF SR[1]<>SR[25],JMP LBL[4] ;
  13:  R[2:spA]=R[2:spA]+1    ;
  14:  JMP LBL[3] ;
  15:  LBL[4] ;
  16:  CALL CA_TEXT(25,'O',0) ;
  17:  IF SR[1]<>SR[25],JMP LBL[5] ;
  18:  R[3:spO]=R[3:spO]+1    ;
  19:  JMP LBL[3] ;
  20:  LBL[5] ;
  21:  CALL CA_TEXT(25,' ',0) ;
  22:  IF SR[1]<>SR[25],JMP LBL[6] ;
  23:  R[4:spSp]=R[4:spSp]+1    ;
  24:  JMP LBL[3] ;
  25:  LBL[6] ;
  26:  CALL CA_TEXT(25,'!',0) ;
  27:  IF SR[1]<>SR[25],JMP LBL[7] ;
  28:  R[5:spBang]=R[5:spBang]+1    ;
  29:  JMP LBL[3] ;
  30:  LBL[7] ;
  31:  R[6:spOther]=R[6:spOther]+1    ;
  32:  LBL[3] ;
  33:  R[1:i]=R[1:i]+1    ;
  34:  JMP LBL[1] ;
  35:  LBL[2] ;
/POS
/END
