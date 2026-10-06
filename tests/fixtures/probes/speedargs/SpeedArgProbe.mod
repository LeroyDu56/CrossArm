MODULE SpeedArgProbe
    ! CrossArm - speed argument probe: see tools/make_speed_arg_probe.py.
    CONST robtarget pA:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pB:=[[1100,250,1000],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pC:=[[1100,250,800],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST jointtarget jStart:=[[0,0,0,0,-90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST speeddata vSpd:=[200,500,5000,1000];
    VAR clock ckSpd;
    VAR num nCalls:=0;
    VAR num nT1:=0;
    VAR num nT2:=0;
    VAR num nT3:=0;
    VAR num nT4:=0;

    PROC SpdMoves(speeddata v,zonedata z)
        MoveJ pA,v,z,tool0;
        MoveL pB,v,z,tool0;
        MoveL pC,v,fine,tool0;
        Incr nCalls;
    ENDPROC

    PROC SpdProbe()
        nCalls:=0;
        MoveAbsJ jStart,v1000,fine,tool0;
        ClkReset ckSpd;
        ClkStart ckSpd;
        SpdMoves v400,z50;
        ClkStop ckSpd;
        nT1:=ClkRead(ckSpd);
        MoveAbsJ jStart,v1000,fine,tool0;
        ClkReset ckSpd;
        ClkStart ckSpd;
        SpdMoves vSpd,z10;
        ClkStop ckSpd;
        nT2:=ClkRead(ckSpd);
        MoveAbsJ jStart,v1000,fine,tool0;
        ClkReset ckSpd;
        ClkStart ckSpd;
        MoveJ pA,v400,z50,tool0;
        MoveL pB,v400,z50,tool0;
        MoveL pC,v400,fine,tool0;
        ClkStop ckSpd;
        nT3:=ClkRead(ckSpd);
        MoveAbsJ jStart,v1000,fine,tool0;
        ClkReset ckSpd;
        ClkStart ckSpd;
        MoveJ pA,vSpd,z10,tool0;
        MoveL pB,vSpd,z10,tool0;
        MoveL pC,vSpd,fine,tool0;
        ClkStop ckSpd;
        nT4:=ClkRead(ckSpd);
    ENDPROC

    PROC Probe()
        VAR iodev file;
        ConfJ\Off;
        ConfL\Off;
        SpdProbe;
        Open "HOME:" \File:="speedargprobe.txt", file \Write;
        Write file, "nCalls " \Num:=nCalls;
        Write file, "nT1 " \Num:=nT1;
        Write file, "nT2 " \Num:=nT2;
        Write file, "nT3 " \Num:=nT3;
        Write file, "nT4 " \Num:=nT4;
        Close file;
    ENDPROC
ENDMODULE
