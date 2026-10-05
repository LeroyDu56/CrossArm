/PROG  STRFACTS
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "string facts";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 28;
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
   1:  CALL CA_TEXT(20,'A',0) ;
   2:  CALL CA_TEXT(21,'a',0) ;
   3:  CALL CA_TEXT(22,'A ',0) ;
   4:  R[70]=0    ;
   5:  IF SR[20]<>SR[21],JMP LBL[1] ;
   6:  R[70]=1    ;
   7:  LBL[1] ;
   8:  R[71]=0    ;
   9:  IF SR[20]<>SR[22],JMP LBL[2] ;
  10:  R[71]=1    ;
  11:  LBL[2] ;
  12:  CALL CA_TEXT(23,'load robot',0) ;
  13:  CALL CA_TEXT(24,'ROBOT',0) ;
  14:  R[72]=FINDSTR SR[23],SR[24]    ;
  15:  CALL CA_TEXT(24,'x',0) ;
  16:  SR[24]=SUBSTR SR[24],2,0 ;
  17:  R[73]=FINDSTR SR[23],SR[24]    ;
  18:  R[74]=2.5    ;
  19:  R[74]=R[74]+.5    ;
  20:  SR[25]=R[74] ;
  21:  R[75]=STRLEN SR[25]    ;
  22:  CALL CA_TEXT(25,'12AB',0) ;
  23:  R[76]=7    ;
  24:  R[76]=SR[25]    ;
  25:  CALL CA_TEXT(25,'ABC',0) ;
  26:  R[77]=7    ;
  27:  R[77]=SR[25]    ;
  28:  R[78]=STRLEN SR[23]    ;
/POS
/END
