/PROG  BFTURN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "BfTurn";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 40;
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
   3:  !RAPID BranchFrameProbe.BfTurn ;
   4:  IF (AR[1]=1) THEN ;
   5:  PR[95,1]=1000    ;
   6:  PR[95,2]=(-100)    ;
   7:  PR[95,3]=700    ;
   8:  PR[95,4]=0    ;
   9:  PR[95,5]=0    ;
  10:  PR[95,6]=0    ;
  11:  !l.35 bfTurn.ufmec:='ROB_1' ;
  12:  ELSE ;
  13:  IF (AR[1]=2) THEN ;
  14:  PR[95,1]=1100    ;
  15:  PR[95,2]=100    ;
  16:  PR[95,3]=700    ;
  17:  PR[95,4]=0    ;
  18:  PR[95,5]=0    ;
  19:  PR[95,6]=90    ;
  20:  !l.38 bfTurn.ufmec:='ROB_1' ;
  21:  ELSE ;
  22:  PAUSE ;
  23:  ABORT ;
  24:  ENDIF ;
  25:  ENDIF ;
  26:  PR[94,1]=0    ;
  27:  PR[94,2]=0    ;
  28:  PR[94,3]=0    ;
  29:  PR[94,4]=5    ;
  30:  PR[94,5]=10    ;
  31:  PR[94,6]=AR[2]    ;
  32:  !l.44 bfTurn.uframe:=PoseMult(pBa ;
  33:  CALL CA_POSEMULT(95,94,93) ;
  34:  UFRAME[3]=PR[93] ;
  35:  !l.45 bfCopy1.uframe:=bfTurn.ufra ;
  36:  PR[93]=UFRAME[3] ;
  37:  UFRAME[1]=PR[93] ;
  38:  !l.46 bfCopy2.uframe:=bfTurn.ufra ;
  39:  PR[93]=UFRAME[3] ;
  40:  UFRAME[2]=PR[93] ;
/POS
/END
