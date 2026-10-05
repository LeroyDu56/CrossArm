/PROG  AWPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "AwProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 37;
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
   1:  !RAPID ArrayWriteProbe.AwProbe ;
   2:  R[7:awSum]=0    ;
   3:  R[8:awCheck]=0    ;
   4:  R[9:awFixed]=0    ;
   5:  R[10:awCorners]=0    ;
   6:  R[11:awSecond]=0    ;
   7:  R[184]=10    ;
   8:  R[185]=20    ;
   9:  R[186]=30    ;
  10:  R[187]=40    ;
  11:  R[188]=50    ;
  12:  CALL AWFILL    ;
  13:  CALL AWADD    ;
  14:  R[185]=R[185]+R[188]    ;
  15:  R[186]=R[186]+1    ;
  16:  R[12:awK]=4    ;
  17:  R[13:Calc8]=R[12:awK]+1    ;
  18:  R[3:NumberIndex]=R[13:Calc8]    ;
  19:  R[3:NumberIndex]=R[3:NumberIndex]+183    ;
  20:  R[14:NumberIndex2]=R[12:awK]    ;
  21:  R[14:NumberIndex2]=R[14:NumberIndex2]+183    ;
  22:  R[R[3]]=R[R[14]]*2    ;
  23:  R[4:Calc1]=R[184]+R[185]    ;
  24:  R[4:Calc1]=R[4:Calc1]+R[186]    ;
  25:  R[4:Calc1]=R[4:Calc1]+R[187]    ;
  26:  R[8:awCheck]=R[4:Calc1]+R[188]    ;
  27:  R[9:awFixed]=R[195]    ;
  28:  R[10:awCorners]=R[200]+R[189]    ;
  29:  R[12:awK]=2    ;
  30:  R[13:Calc8]=R[12:awK]+2    ;
  31:  R[3:NumberIndex]=R[12:awK]    ;
  32:  R[3:NumberIndex]=R[3:NumberIndex]*4    ;
  33:  R[3:NumberIndex]=R[3:NumberIndex]+R[13:Calc8]    ;
  34:  R[3:NumberIndex]=R[3:NumberIndex]+184    ;
  35:  R[14:NumberIndex2]=R[12:awK]    ;
  36:  R[14:NumberIndex2]=R[14:NumberIndex2]+183    ;
  37:  R[11:awSecond]=R[R[3]]+R[R[14]]    ;
/POS
/END
