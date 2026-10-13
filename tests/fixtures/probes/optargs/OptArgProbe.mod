MODULE OptArgProbe
    ! CrossArm - optional-argument probe: see tools/make_optional_arg_probe.py.
    VAR num nBefore:=0;
    VAR num nSpeedSum:=0;
    VAR num nAbsent:=0;
    VAR num nFast:=0;
    VAR num nLabel:=0;
    VAR num nSlow:=0;
    VAR num nCount:=0;
    VAR num nKept:=0;
    VAR num nBand:=0;
    VAR num nAfter:=0;

    PROC Station(num nId\num Speed\bool Fast\string Label\INOUT num Count\switch Slow)
        IF Present(Speed) THEN
            nSpeedSum:=nSpeedSum+Speed;
        ELSE
            nAbsent:=nAbsent+1;
        ENDIF
        IF Present(Fast) AND Fast=TRUE THEN
            nFast:=nFast+1;
        ENDIF
        IF Present(Label) nLabel:=nLabel+1;
        IF Present(Slow) nSlow:=nSlow+1;
        IF Present(Count) THEN
            Count:=Count+nId;
        ENDIF
    ENDPROC

    PROC Relay(\num Speed)
        Station 9\Speed?Speed;
    ENDPROC

    FUNC bool InBand(num nValue,num nRef\num Tol)
        IF Present(Tol) THEN
            IF nValue>=nRef-Tol AND nValue<=nRef+Tol RETURN TRUE;
            RETURN FALSE;
        ENDIF
        RETURN nValue=nRef;
    ENDFUNC

    PROC OptArgProbe()
        nBefore:=1;
        nCount:=5;
        nKept:=7;
        Station 3\Speed:=200\Fast:=TRUE\Count:=nCount;
        Station 4\Fast:=FALSE\Slow;
        Station 5\Label:="AB";
        Station 6;
        Relay\Speed:=50;
        Relay;
        IF InBand(nCount,10\Tol:=3) nBand:=nBand+1;
        IF InBand(nCount,10) nBand:=nBand+10;
        IF InBand(nCount,8) nBand:=nBand+100;
        nAfter:=1;
    ENDPROC
ENDMODULE
