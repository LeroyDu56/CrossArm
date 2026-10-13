/PROG  RTPREP
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RtPrep";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 9;
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
   3:  !RAPID RtcpProbe.RtPrep ;
   4:  UFRAME_NUM=1 ;
   5:  UTOOL_NUM=1 ;
   6:J P[1] 11% FINE    ;
   7:  UFRAME_NUM=0 ;
   8:  UTOOL_NUM=2 ;
   9:  PR[99]=LPOS    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    30.872  mm,	Y =   -39.331  mm,	Z =     0.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   165.000 deg
};
/END
