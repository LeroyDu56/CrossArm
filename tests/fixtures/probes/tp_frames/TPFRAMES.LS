/PROG  TPFRAMES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 61;
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
   1:  R[41]=0 ;
   2:  UFRAME_NUM=0 ;
   3:  PR[29]=LPOS ;
   4:  PR[29]=PR[29]-PR[29] ;
   5:  UTOOL[9]=PR[29] ;
   6:  UTOOL_NUM=9 ;
   7:J P[1] 10% FINE ;
   8:  PR[30]=LPOS ;
   9:  PR[21]=PR[29] ;
  10:  PR[21,1]=100 ;
  11:  PR[21,2]=(-50) ;
  12:  PR[21,3]=30 ;
  13:  PR[21,4]=10 ;
  14:  PR[21,6]=90 ;
  15:  PR[22]=PR[29] ;
  16:  PR[22,1]=50 ;
  17:  PR[22,2]=20 ;
  18:  PR[22,5]=20 ;
  19:  PR[22,6]=30 ;
  20:  PR[23]=PR[29] ;
  21:  PR[23,1]=10 ;
  22:  PR[23,2]=20 ;
  23:  PR[23,3]=30 ;
  24:  PR[23,4]=5 ;
  25:  PR[23,6]=10 ;
  26:  PR[24]=PR[29] ;
  27:  PR[24,1]=10 ;
  28:  PR[25]=PR[29] ;
  29:  PR[25,1]=20 ;
  30:  PR[25,3]=50 ;
  31:  PR[25,4]=5 ;
  32:  PR[25,6]=10 ;
  33:  R[41]=1 ;
  34:  PR[31]=PR[21]+PR[22] ;
  35:  UFRAME[5]=PR[21] ;
  36:  PR[32]=UFRAME[5] ;
  37:  UFRAME_NUM=5 ;
  38:  PR[34]=LPOS ;
  39:  UFRAME_NUM=0 ;
  40:  R[41]=2 ;
  41:L PR[30] 100mm/sec FINE Offset,PR[23] ;
  42:  PR[33]=LPOS ;
  43:J P[1] 10% FINE ;
  44:  R[41]=3 ;
  45:  OFFSET CONDITION PR[24],UFRAME[5] ;
  46:L PR[30] 100mm/sec FINE Offset ;
  47:  PR[38]=LPOS ;
  48:J P[1] 10% FINE ;
  49:  R[41]=4 ;
  50:L PR[30] 100mm/sec FINE Tool_Offset,PR[25] ;
  51:  PR[39]=LPOS ;
  52:J P[1] 10% FINE ;
  53:  R[41]=5 ;
  54:  UFRAME_NUM=5 ;
  55:L PR[34] 100mm/sec FINE Offset,PR[23] ;
  56:  UFRAME_NUM=0 ;
  57:  PR[40]=LPOS ;
  58:J P[1] 10% FINE ;
  59:  R[41]=6 ;
  60:  PR[36]=PR[21]*PR[22] ;
  61:  R[41]=7 ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 9,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
/END
