/PROG  RECPROBR
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RecProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 50;
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
   1:  R[13]=400 ;
   2:  !RAPID RecordProbe.RecProbe ;
   3:  R[6:nSteps]=0    ;
   4:  R[5:nBusy]=0    ;
   5:  R[8:nSaved]=0    ;
   6:  R[4:nBad]=0    ;
   7:  R[9:nCopy]=0    ;
   8:  R[7:tallyLast.n]=0    ;
   9:  F[2]=(OFF) ;
  10:  R[2:recCtrl.state]=0    ;
  11:  CALL RECINIT    ;
  12:  LBL[1] ;
  13:  IF (R[2:recCtrl.state]=3) THEN ;
  14:  JMP LBL[2] ;
  15:  ENDIF ;
  16:  SELECT R[2:recCtrl.state]=0,CALL RECSTEPA ;
  17:         =1,CALL RECSTEPB ;
  18:         ELSE,JMP LBL[4] ;
  19:  JMP LBL[3] ;
  20:  LBL[4] ;
  21:  R[2:recCtrl.state]=3    ;
  22:  LBL[3] ;
  23:  CALL RECCOUNT    ;
  24:  JMP LBL[1] ;
  25:  LBL[2] ;
  26:  R[8:nSaved]=307    ;
  27:  !l.88 IF always TRUE: no test ;
  28:  R[8:nSaved]=R[8:nSaved]+1000    ;
  29:  R[10:tallyCopy.n]=R[7:tallyLast.n]    ;
  30:  F[3]=(F[2]) ;
  31:  IF (F[3]=ON) THEN ;
  32:  R[9:nCopy]=R[10:tallyCopy.n]+100    ;
  33:  ELSE ;
  34:  R[9:nCopy]=R[10:tallyCopy.n]    ;
  35:  ENDIF ;
  36:  UFRAME_NUM=0 ;
  37:  UTOOL_NUM=1 ;
  38:J P[1] 22% FINE    ;
  39:J P[2] 22% FINE    ;
  40:  TIMER[1]=RESET ;
  41:  TIMER[1]=START ;
  42:L P[3] R[13]mm/sec FINE    ;
  43:  TIMER[1]=STOP ;
  44:  R[11:nTime]=TIMER[1]    ;
  45:  TIMER[1]=RESET ;
  46:  TIMER[1]=START ;
  47:L P[4] R[13]mm/sec CNT100    ;
  48:L P[2] R[13]mm/sec FINE    ;
  49:  TIMER[1]=STOP ;
  50:  R[12:nTime2]=TIMER[1]    ;
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
