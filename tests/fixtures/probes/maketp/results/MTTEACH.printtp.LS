/PROG  MTTEACH
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "MtTeach         ";
PROG_SIZE	= 559;
CREATE		= DATE 26-10-06  TIME 16:17:00;
MODIFIED	= DATE 26-10-06  TIME 16:17:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 4;
MEMORY_SIZE	= 915;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
LOCAL_REGISTERS	= 0,0,0;
/MN
   1:  !RAPID MakeTpProbe.MtTeach ;
   2:  UFRAME_NUM=1 ;
   3:  UTOOL_NUM=2 ;
   4:L P[1] 200mm/sec FINE    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 1',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
