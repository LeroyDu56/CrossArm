MODULE WaitProbe
    ! CrossArm - wait probe: see tools/make_wait_probe.py.
    VAR num nTimeouts:=0;
    VAR num nAfter:=0;
    VAR num nRetries:=0;
    VAR bool bNever:=FALSE;

    PROC WaitProbe()
        nTimeouts:=0;
        nAfter:=0;
        nRetries:=0;
        bNever:=FALSE;
        WaitNext;
        WaitRetry;
        nAfter:=nAfter+100;
    ENDPROC

    PROC WaitNext()
        WaitUntil bNever=TRUE\MaxTime:=0.5;
        nAfter:=nAfter+1;
        WaitDI diNever,1\MaxTime:=0.3;
        nAfter:=nAfter+1;
    ERROR
        TEST ERRNO
        CASE ERR_WAIT_MAXTIME:
            TRYNEXT;
        ENDTEST
    ENDPROC

    PROC WaitRetry()
        WaitUntil bNever\MaxTime:=0.2;
        nAfter:=nAfter+10;
    ERROR
        IF ERRNO=ERR_WAIT_MAXTIME THEN
            IF nRetries<2 THEN
                nRetries:=nRetries+1;
                RETRY;
            ELSE
                nTimeouts:=nTimeouts+1;
                RETURN;
            ENDIF
        ENDIF
        RAISE;
    ENDPROC
ENDMODULE
