/PROG  FTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FtProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 46;
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
   1:  !CrossArm EVALUATION copy ;
   2:  !production use needs a licence ;
   3:  !RAPID FuncTextProbe.FtProbe ;
   4:  R[1:ftDone]=0    ;
   5:  R[2:ftHits]=0    ;
   6:  R[3:ftPart]=0    ;
   7:  FOR R[4:k]=1 TO 3 ;
   8:  R[3:ftPart]=R[3:ftPart]+7    ;
   9:  SR[25]=R[3:ftPart] ;
  10:  CALL FTPAD(SR[25],5,1,'0',2) ;
  11:  SR[1]=SR[2] ;
  12:  CALL CA_TEXT(25,'00007',0) ;
  13:  IF SR[1]<>SR[25],JMP LBL[1] ;
  14:  R[2:ftHits]=R[2:ftHits]+1    ;
  15:  LBL[1] ;
  16:  CALL CA_TEXT(25,'00021',0) ;
  17:  IF SR[1]<>SR[25],JMP LBL[2] ;
  18:  R[2:ftHits]=R[2:ftHits]+100    ;
  19:  LBL[2] ;
  20:  ENDFOR ;
  21:  R[200:ftLen1]=STRLEN SR[1]    ;
  22:  SR[25]=R[3:ftPart] ;
  23:  CALL FTPAD(SR[25],4,0,'',2) ;
  24:  CALL FTJOIN(SR[1],'9',4) ;
  25:  CALL CA_TEXT(3,'#',0) ;
  26:  SR[3]=SR[3]+SR[2] ;
  27:  CALL CA_TEXT(3,'-',1) ;
  28:  SR[3]=SR[3]+SR[4] ;
  29:  R[199:ftLen2]=STRLEN SR[3]    ;
  30:  CALL CA_TEXT(25,'#  21-00021/9',0) ;
  31:  IF SR[3]<>SR[25],JMP LBL[3] ;
  32:  R[2:ftHits]=R[2:ftHits]+10    ;
  33:  LBL[3] ;
  34:  CALL FTJOIN(SR[3],SR[3],4) ;
  35:  CALL FTREPEAT('12345',10,6) ;
  36:  CALL FTJOIN(SR[4],SR[6],4) ;
  37:  SR[5]=SR[4] ;
  38:  R[198:ftLen3]=STRLEN SR[5]    ;
  39:  CALL FTPAD('',3,0,'',2) ;
  40:  R[197:ftLen4]=STRLEN SR[2]    ;
  41:  CALL FTPAD('12',2,0,'',2) ;
  42:  CALL CA_TEXT(25,'12',0) ;
  43:  IF SR[2]<>SR[25],JMP LBL[4] ;
  44:  R[2:ftHits]=R[2:ftHits]+1000    ;
  45:  LBL[4] ;
  46:  R[1:ftDone]=1    ;
/POS
/END
