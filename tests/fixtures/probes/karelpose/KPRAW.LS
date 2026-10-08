/PROG  KPRAW
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "KAREL pose probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 49;
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
   1:  UFRAME_NUM=0 ;
   2:  UTOOL_NUM=1 ;
   3:  R[81]=0    ;
   4:  R[82]=10    ;
   5:  R[83]=2.5    ;
   6:  PR[81]=LPOS    ;
   7:  PR[81,1]=100    ;
   8:  PR[81,2]=(-50)    ;
   9:  PR[81,3]=300    ;
  10:  PR[81,4]=30    ;
  11:  PR[81,5]=(-20)    ;
  12:  PR[81,6]=45    ;
  13:  PR[84]=LPOS    ;
  14:  PR[84,1]=600    ;
  15:  PR[84,2]=100    ;
  16:  PR[84,3]=400    ;
  17:  PR[84,4]=0    ;
  18:  PR[84,5]=0    ;
  19:  PR[84,6]=0    ;
  20:  PR[85]=LPOS    ;
  21:  PR[85,1]=800    ;
  22:  PR[85,2]=250    ;
  23:  PR[85,3]=420    ;
  24:  PR[85,4]=0    ;
  25:  PR[85,5]=0    ;
  26:  PR[85,6]=0    ;
  27:  PR[86]=LPOS    ;
  28:  PR[86,1]=650    ;
  29:  PR[86,2]=300    ;
  30:  PR[86,3]=380    ;
  31:  PR[86,4]=0    ;
  32:  PR[86,5]=0    ;
  33:  PR[86,6]=0    ;
  34:  PR[87]=LPOS    ;
  35:  PR[87,1]=603    ;
  36:  PR[87,2]=100    ;
  37:  PR[87,3]=400    ;
  38:  PR[87,4]=0    ;
  39:  PR[87,5]=0    ;
  40:  PR[87,6]=0    ;
  41:  CALL CA_POSEINV(81,88) ;
  42:  CALL CA_RELTOOL(81,89,R[82],20,R[83],30,(-20),45) ;
  43:  CALL CA_RELTOOL(81,90,0,0,(-15),0,0,(-90)) ;
  44:  CALL CA_RELTOOL(81,91,5,0,0,200,120,0) ;
  45:  CALL CA_DEFFRAME(84,85,86,92,1) ;
  46:  CALL CA_DEFFRAME(84,85,86,93,2) ;
  47:  CALL CA_DEFFRAME(84,85,86,94,3) ;
  48:  CALL CA_POSEMULT(81,88,95) ;
  49:  R[81]=1    ;
/POS
/END
