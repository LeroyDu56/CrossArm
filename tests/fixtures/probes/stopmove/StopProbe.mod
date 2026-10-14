MODULE StopProbe
    ! CrossArm - StopMove probe: see tools/make_stopmove_probe.py.
    CONST robtarget smStart:=[[1100,-200,800],[0,0.3826834,0.9238795,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget smCorner:=[[1400,-200,800],[0,0.3826834,0.9238795,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget smEnd:=[[1400,200,800],[0,0.3826834,0.9238795,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR intnum iStopA;
    VAR intnum iHoldB;
    VAR intnum iEnable;
    VAR num nPaused:=0;
    VAR num nHolds:=0;
    VAR num nEnables:=0;
    VAR num nDone:=0;

    PROC StopProbe()
        nPaused:=0;
        nHolds:=0;
        nEnables:=0;
        nDone:=0;
        IDelete iStopA;
        IDelete iHoldB;
        IDelete iEnable;
        MoveJ smStart,v1000,fine,tool0;
        CONNECT iStopA WITH tStopA;
        ISignalDI diStopA,1,iStopA;
        MoveL smCorner,v100,fine,tool0;
        IDelete iStopA;
        MoveL smStart,v1000,fine,tool0;
        MoveL smCorner,v100,z100,tool0;
        StopMove;
        WaitTime 2;
        StartMove;
        CONNECT iHoldB WITH tHoldB;
        ISignalDI diHoldB,1,iHoldB;
        CONNECT iEnable WITH tEnable;
        ISignalDI diEnable,edge,iEnable;
        MoveL smEnd,v100,fine,tool0;
        IDelete iHoldB;
        IDelete iEnable;
        nDone:=1;
    ENDPROC

    TRAP tStopA
        StopMove;
        nPaused:=nPaused+1;
        StopWait;
    ENDTRAP

    PROC StopWait()
        WaitDI diStopA,0;
        StartMove;
    ENDPROC

    TRAP tHoldB
        StopMove;
        ClearPath;
        nHolds:=nHolds+1;
    ENDTRAP

    TRAP tEnable
        nEnables:=nEnables+1;
        IF diEnable=1 THEN
            StartMove;
        ELSE
            StopMove;
        ENDIF
    ENDTRAP
ENDMODULE
