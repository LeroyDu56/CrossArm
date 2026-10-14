/PROG  TALENGTH
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "TaLength";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 13;
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
   3:  !RAPID ToolArgProbe.TaLength ;
   4:  !l.54 t.tframe.trans.z:=nLen ;
   5:  PR[92]=UTOOL[AR[1]] ;
   6:  PR[92,3]=AR[2]    ;
   7:  UTOOL[AR[1]]=PR[92] ;
   8:  !l.55 t.tframe.rot:=[1,0,0,0] ;
   9:  PR[92]=UTOOL[AR[1]] ;
  10:  PR[92,4]=0    ;
  11:  PR[92,5]=0    ;
  12:  PR[92,6]=0    ;
  13:  UTOOL[AR[1]]=PR[92] ;
/POS
/END
