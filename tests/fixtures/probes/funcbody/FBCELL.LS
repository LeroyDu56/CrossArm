/PROG  FBCELL
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FbCell";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 11;
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
   3:  !RAPID FuncBodyProbe.FbCell ;
   4:  PR[96]=P[1]    ;
   5:  R[10:Calc2]=AR[2]-1    ;
   6:  R[10:Calc2]=R[10:Calc2]*20    ;
   7:  PR[96,1]=1000+R[10:Calc2]    ;
   8:  R[10:Calc2]=AR[1]-1    ;
   9:  R[10:Calc2]=R[10:Calc2]*30    ;
  10:  PR[96,2]=(-100)+R[10:Calc2]    ;
  11:  PR[AR[3]]=PR[96]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =  -100.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
