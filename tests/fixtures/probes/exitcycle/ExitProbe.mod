MODULE ExitProbe
    ! CrossArm - ExitCycle probe: see tools/make_exitcycle_probe.py.
    CONST robtarget xpStart:=[[1100,-200,800],[0,0.3826834,0.9238795,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget xpCorner:=[[1400,-200,800],[0,0.3826834,0.9238795,0],[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    VAR intnum iAbort;
    VAR num nCycles;
    VAR num nTraps;
    VAR num nAfter;
    VAR num nDone;

    PROC ExitProbe()
        Incr nCycles;
        IDelete iAbort;
        MoveJ xpStart,v1000,fine,tool0;
        IF nCycles=1 THEN
            CONNECT iAbort WITH tAbort;
            ISignalDI diAbort,1,iAbort;
            MoveL xpCorner,v60,fine,tool0;
        ENDIF
        IDelete iAbort;
        MoveL xpCorner,v200,z100,tool0;
        Leave;
        nDone:=nCycles;
    ENDPROC

    PROC Leave()
        IF nCycles=2 THEN
            ExitCycle;
            nAfter:=1;
        ENDIF
    ENDPROC

    TRAP tAbort
        Incr nTraps;
        StopMove;
        ClearPath;
        ExitCycle;
    ENDTRAP
ENDMODULE
