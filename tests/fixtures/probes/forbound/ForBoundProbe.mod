MODULE ForBoundProbe
    ! CrossArm - FOR-bound probe: see tools/make_for_bound_probe.py.
    VAR num nBefore:=0;
    VAR num nCount:=0;
    VAR num nTwo:=0;
    VAR num nTo:=0;
    VAR num nDown:=0;
    VAR num nCalc:=0;
    VAR num nNest:=0;
    VAR num nShrink:=0;
    VAR num nNone:=0;
    VAR num nGated:=0;
    VAR num nStepSum:=0;
    VAR num nStepDown:=0;
    VAR num nQuarter:=0;
    VAR num nAfter:=0;

    FUNC num CycleCount()
        IF OpMode()=OP_AUTO RETURN 5;
        RETURN 2;
    ENDFUNC

    PROC ForBoundProbe()
        nBefore:=1;
        nCount:=4;
        nTwo:=2;
        FOR i FROM 1 TO nCount DO
            nTo:=nTo+1;
        ENDFOR
        FOR i FROM nCount TO 2 STEP -1 DO
            nDown:=nDown+1;
        ENDFOR
        FOR i FROM 2 TO nCount*2-3 DO
            nCalc:=nCalc+1;
        ENDFOR
        FOR i FROM 1 TO nTwo+1 DO
            FOR j FROM nTwo-1 TO nTwo DO
                nNest:=nNest+1;
            ENDFOR
        ENDFOR
        FOR i FROM 1 TO nCount DO
            nCount:=nCount-1;
            nShrink:=nShrink+1;
        ENDFOR
        FOR i FROM nTwo TO nTwo-1 DO
            nNone:=nNone+1;
        ENDFOR
        FOR i FROM 0 TO 20 STEP 4 DO
            nStepSum:=nStepSum+i;
        ENDFOR
        FOR i FROM nTwo*5 TO nTwo STEP -3 DO
            nStepDown:=nStepDown+1;
        ENDFOR
        FOR i FROM 0 TO 1 STEP 0.25 DO
            nQuarter:=nQuarter+1;
        ENDFOR
        FOR i FROM 1 TO CycleCount() DO
            nGated:=nGated+1;
        ENDFOR
        nAfter:=1;
    ENDPROC
ENDMODULE
