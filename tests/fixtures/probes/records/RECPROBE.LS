/PROG  RECPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RecProbe";
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
   1:  !RAPID RecordProbe.RecProbe ;
   2:  R[6:nSteps]=0    ;
   3:  R[5:nBusy]=0    ;
   4:  R[8:nSaved]=0    ;
   5:  R[4:nBad]=0    ;
   6:  R[9:nCopy]=0    ;
   7:  R[7:tallyLast.n]=0    ;
   8:  F[2]=(OFF) ;
   9:  R[2:recCtrl.state]=0    ;
  10:  CALL RECINIT    ;
  11:  LBL[1] ;
  12:  IF (R[2:recCtrl.state]=3) THEN ;
  13:  JMP LBL[2] ;
  14:  ENDIF ;
  15:  SELECT R[2:recCtrl.state]=0,CALL RECSTEPA ;
  16:         =1,CALL RECSTEPB ;
  17:         ELSE,JMP LBL[4] ;
  18:  JMP LBL[3] ;
  19:  LBL[4] ;
  20:  R[2:recCtrl.state]=3    ;
  21:  LBL[3] ;
  22:  CALL RECCOUNT    ;
  23:  JMP LBL[1] ;
  24:  LBL[2] ;
  25:  R[8:nSaved]=307    ;
  26:  !l.88 IF always TRUE: no test ;
  27:  R[8:nSaved]=R[8:nSaved]+1000    ;
  28:  R[10:tallyCopy.n]=R[7:tallyLast.n]    ;
  29:  F[3]=(F[2]) ;
  30:  IF (F[3]=ON) THEN ;
  31:  R[9:nCopy]=R[10:tallyCopy.n]+100    ;
  32:  ELSE ;
  33:  R[9:nCopy]=R[10:tallyCopy.n]    ;
  34:  ENDIF ;
  35:  UFRAME_NUM=0 ;
  36:  UTOOL_NUM=1 ;
  37:J P[1] 22% FINE    ;
  38:J P[2] 22% FINE    ;
  39:  TIMER[1]=RESET ;
  40:  TIMER[1]=START ;
  41:L P[3] 400mm/sec FINE    ;
  42:  TIMER[1]=STOP ;
  43:  R[11:nTime]=TIMER[1]    ;
  44:  TIMER[1]=RESET ;
  45:  TIMER[1]=START ;
  46:L P[4] 400mm/sec CNT100    ;
  47:L P[2] 400mm/sec FINE    ;
  48:  TIMER[1]=STOP ;
  49:  R[12:nTime2]=TIMER[1]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
