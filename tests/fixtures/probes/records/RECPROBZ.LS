/PROG  RECPROBZ
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RecProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 51;
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
   2:  R[14]=100 ;
   3:  !RAPID RecordProbe.RecProbe ;
   4:  R[6:nSteps]=0    ;
   5:  R[5:nBusy]=0    ;
   6:  R[8:nSaved]=0    ;
   7:  R[4:nBad]=0    ;
   8:  R[9:nCopy]=0    ;
   9:  R[7:tallyLast.n]=0    ;
  10:  F[2]=(OFF) ;
  11:  R[2:recCtrl.state]=0    ;
  12:  CALL RECINIT    ;
  13:  LBL[1] ;
  14:  IF (R[2:recCtrl.state]=3) THEN ;
  15:  JMP LBL[2] ;
  16:  ENDIF ;
  17:  SELECT R[2:recCtrl.state]=0,CALL RECSTEPA ;
  18:         =1,CALL RECSTEPB ;
  19:         ELSE,JMP LBL[4] ;
  20:  JMP LBL[3] ;
  21:  LBL[4] ;
  22:  R[2:recCtrl.state]=3    ;
  23:  LBL[3] ;
  24:  CALL RECCOUNT    ;
  25:  JMP LBL[1] ;
  26:  LBL[2] ;
  27:  R[8:nSaved]=307    ;
  28:  !l.88 IF always TRUE: no test ;
  29:  R[8:nSaved]=R[8:nSaved]+1000    ;
  30:  R[10:tallyCopy.n]=R[7:tallyLast.n]    ;
  31:  F[3]=(F[2]) ;
  32:  IF (F[3]=ON) THEN ;
  33:  R[9:nCopy]=R[10:tallyCopy.n]+100    ;
  34:  ELSE ;
  35:  R[9:nCopy]=R[10:tallyCopy.n]    ;
  36:  ENDIF ;
  37:  UFRAME_NUM=0 ;
  38:  UTOOL_NUM=1 ;
  39:J P[1] 22% FINE    ;
  40:J P[2] 22% FINE    ;
  41:  TIMER[1]=RESET ;
  42:  TIMER[1]=START ;
  43:L P[3] R[13]mm/sec FINE    ;
  44:  TIMER[1]=STOP ;
  45:  R[11:nTime]=TIMER[1]    ;
  46:  TIMER[1]=RESET ;
  47:  TIMER[1]=START ;
  48:L P[4] R[13]mm/sec CNT R[14]    ;
  49:L P[2] R[13]mm/sec FINE    ;
  50:  TIMER[1]=STOP ;
  51:  R[12:nTime2]=TIMER[1]    ;
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
