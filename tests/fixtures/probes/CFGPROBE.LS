/PROG  CFGPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CONFIG probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 17;
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
   1:  !CrossArm CONFIG probe ;
   2:J P[1] 10% FINE    ;
   3:J P[2] 10% FINE    ;
   4:J P[3] 10% FINE    ;
   5:J P[4] 10% FINE    ;
   6:J P[5] 10% FINE    ;
   7:J P[6] 10% FINE    ;
   8:J P[7] 10% FINE    ;
   9:J P[8] 10% FINE    ;
  10:J P[9] 10% FINE    ;
  11:J P[10] 10% FINE    ;
  12:J P[11] 10% FINE    ;
  13:J P[12] 10% FINE    ;
  14:J P[13] 10% FINE    ;
  15:J P[14] 10% FINE    ;
  16:J P[15] 10% FINE    ;
  17:J P[16] 10% FINE    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -30.000 deg,	J6=     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    30.000 deg,	J6=     0.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=   185.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=  -185.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=   190.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=  -190.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=   350.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=    40.000 deg,	J3=    60.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=    40.000 deg,	J3=   -60.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[12]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -60.000 deg,	J3=   -80.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[13]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -60.000 deg,	J3=    80.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[14]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=    60.000 deg,	J3=    80.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,	
	J1=    90.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[16]{
   GP1:
	UF : 0, UT : 1,	
	J1=  -150.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
/END
