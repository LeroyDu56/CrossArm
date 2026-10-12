MODULE RaiseProbe
    ! CrossArm - raise probe: see tools/make_raise_probe.py.
    VAR errnum ERR_RP_A:=-1;
    VAR errnum ERR_RP_B:=-1;
    CONST errnum ERR_RP_C:=7;
    VAR num rpTries:=0;
    VAR num rpTrace:=0;
    VAR num rpSkip:=0;
    VAR num rpRet:=0;
    VAR num rpPass:=0;
    VAR num rpCode:=0;
    VAR num rpLimit:=0;
    VAR num rpDone:=0;

    PROC RpProbe()
        BookErrNo ERR_RP_A;
        BookErrNo ERR_RP_B;
        rpTries:=0;
        rpTrace:=0;
        rpSkip:=0;
        rpRet:=0;
        rpPass:=0;
        rpCode:=0;
        rpDone:=0;
        RpRetry;
        RpNext;
        RpReturn;
        rpRet:=rpRet+10;
        RpOuter;
        RpBody;
        rpDone:=1;
    ENDPROC

    PROC RpFlaky()
        rpTries:=rpTries+1;
        IF rpTries<3 THEN
            RAISE ERR_RP_A;
        ENDIF
    ERROR
        RAISE;
    ENDPROC

    PROC RpRetry()
        RpFlaky;
        rpTrace:=rpTrace+1;
    ERROR
        IF ERRNO=ERR_RP_A THEN
            RETRY;
        ENDIF
    ENDPROC

    PROC RpOdd(num k)
        IF k MOD 2=1 THEN
            RAISE ERR_RP_B;
        ENDIF
    ERROR
        RAISE;
    ENDPROC

    PROC RpNext()
        FOR i FROM 1 TO 5 DO
            RpOdd i;
            rpSkip:=rpSkip+10;
        ENDFOR
    ERROR
        IF ERRNO=ERR_RP_B THEN
            rpSkip:=rpSkip+1;
            TRYNEXT;
        ENDIF
    ENDPROC

    PROC RpReturn()
        RpOdd 1;
        rpRet:=rpRet+100;
    ERROR
        IF ERRNO=ERR_RP_B THEN
            rpRet:=rpRet+1;
            RETURN;
        ENDIF
    ENDPROC

    PROC RpMiddle()
        RpOdd 3;
        rpPass:=rpPass+100;
    ERROR
        IF ERRNO=ERR_RP_B THEN
            rpPass:=rpPass+1;
        ENDIF
        RAISE;
    ENDPROC

    PROC RpOuter()
        RpMiddle;
        rpPass:=rpPass+1000;
    ERROR
        IF ERRNO=ERR_RP_B THEN
            rpPass:=rpPass+10;
            TRYNEXT;
        ENDIF
    ENDPROC

    PROC RpBody()
        rpCode:=1;
        RAISE ERR_RP_C;
        rpCode:=rpCode+20;
    ERROR
        TEST ERRNO
        CASE ERR_RP_C:
            rpCode:=rpCode+ERRNO;
            TRYNEXT;
        ENDTEST
    ENDPROC

    PROC RpAlways()
        rpLimit:=rpLimit+1;
        RAISE ERR_RP_A;
    ERROR
        RAISE;
    ENDPROC

    PROC RpLimit()
        rpLimit:=0;
        RpAlways;
        rpLimit:=rpLimit+100;
    ERROR
        IF ERRNO=ERR_RP_A THEN
            RETRY;
        ENDIF
    ENDPROC
ENDMODULE
