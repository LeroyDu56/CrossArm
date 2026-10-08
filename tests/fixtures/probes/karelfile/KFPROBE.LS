/PROG  KFPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "KfProbe";
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
   1:  !RAPID KarelFileProbe.KfProbe ;
   2:  R[1:kfDone]=0    ;
   3:  CALL CA_FILE(1,2,1,'UD1:kfprobe.txt') ;
   4:  CALL CA_FILE(2,2,1,'CrossArm file probe') ;
   5:  CALL CA_FILE(2,2,1,'it`s a,b;c (x)') ;
   6:  CALL CA_FILE(2,2,1,'01234567890123456789012345678901234567','89012345678901234567890123456789') ;
   7:  R[3:kfV]=.333333    ;
   8:  CALL CA_FILE(2,2,1,'n0 ',R[3]) ;
   9:  R[3:kfV]=2.5    ;
  10:  CALL CA_FILE(2,2,1,'n1 ',R[3]) ;
  11:  R[3:kfV]=123456.7    ;
  12:  CALL CA_FILE(2,2,1,'n2 ',R[3]) ;
  13:  R[3:kfV]=1234567    ;
  14:  CALL CA_FILE(2,2,1,'n3 ',R[3]) ;
  15:  R[3:kfV]=(-.000012)    ;
  16:  CALL CA_FILE(2,2,1,'n4 ',R[3]) ;
  17:  R[3:kfV]=(-7)    ;
  18:  CALL CA_FILE(2,2,1,'n5 ',R[3]) ;
  19:  R[3:kfV]=.3    ;
  20:  CALL CA_FILE(2,2,1,'n6 ',R[3]) ;
  21:  R[3:kfV]=99.99999    ;
  22:  CALL CA_FILE(2,2,1,'n7 ',R[3]) ;
  23:  R[3:kfV]=.0123456    ;
  24:  CALL CA_FILE(2,2,1,'n8 ',R[3]) ;
  25:  R[3:kfV]=12.345678    ;
  26:  CALL CA_FILE(2,2,1,'n9 ',R[3]) ;
  27:  R[3:kfV]=3.141593    ;
  28:  CALL CA_FILE(2,2,1,'n10 ',R[3]) ;
  29:  R[3:kfV]=(-.3)    ;
  30:  CALL CA_FILE(2,2,1,'n11 ',R[3]) ;
  31:  R[3:kfV]=.000004    ;
  32:  CALL CA_FILE(2,2,1,'n12 ',R[3]) ;
  33:  R[3:kfV]=0    ;
  34:  CALL CA_FILE(2,2,1,'n13 ',R[3]) ;
  35:  R[3:kfV]=100    ;
  36:  CALL CA_FILE(2,2,1,'n14 ',R[3]) ;
  37:  CALL CA_FILE(2,2,0,'no line, ') ;
  38:  CALL CA_FILE(2,2,1,'end') ;
  39:  CALL CA_FILE(3,2) ;
  40:  CALL CA_FILE(1,2,2,'UD1:kfprobe.txt') ;
  41:  CALL KFLINE('appended',3) ;
  42:  CALL CA_FILE(3,2) ;
  43:  R[4:kfI]=2    ;
  44:  R[5:NumberIndex]=R[4:kfI]    ;
  45:  R[5:NumberIndex]=R[5:NumberIndex]+198    ;
  46:  CALL CA_FILE(1,R[5],1,'UD1:kfsecond.txt') ;
  47:  R[5:NumberIndex]=R[4:kfI]    ;
  48:  R[5:NumberIndex]=R[5:NumberIndex]+198    ;
  49:  CALL CA_FILE(2,R[5],1,'second') ;
  50:  R[5:NumberIndex]=R[4:kfI]    ;
  51:  R[5:NumberIndex]=R[5:NumberIndex]+198    ;
  52:  CALL CA_FILE(3,R[5]) ;
  53:  CALL CA_FILE(1,199,2,'UD1:kfsecond.txt') ;
  54:  CALL CA_FILE(2,199,1,'added') ;
  55:  CALL CA_FILE(3,199) ;
  56:  CALL CA_FILE(1,2,1,'UD1:kfthird.txt') ;
  57:  CALL CA_FILE(2,2,1,'first') ;
  58:  CALL CA_FILE(3,2) ;
  59:  CALL CA_FILE(1,2,1,'UD1:kfthird.txt') ;
  60:  CALL CA_FILE(2,2,1,'rewritten') ;
  61:  CALL CA_FILE(3,2) ;
  62:  R[1:kfDone]=1    ;
/POS
/END
