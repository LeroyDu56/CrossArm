MODULE CondProbe
    ! CrossArm - condition probe: see tools/make_condition_probe.py.
    VAR num nMode:=0;
    VAR bool bArmed:=FALSE;
    VAR num nHits:=0;
    VAR num nMiss:=0;
    VAR num nGroup:=0;
    VAR num nLoops:=0;
    VAR num nIo:=0;

    PROC CondProbe()
        nHits:=0;
        nMiss:=0;
        nGroup:=0;
        nLoops:=0;
        nMode:=0;
        bArmed:=TRUE;
        IF Ready()=TRUE THEN
            nHits:=nHits+1;
        ENDIF
        IF Blocked()=FALSE AND NOT Armed() THEN
            nMiss:=nMiss+1;
        ENDIF
        nMode:=1;
        IF Blocked()=FALSE AND NOT Armed() THEN
            nHits:=nHits+10;
        ENDIF
        IF nMode>0 AND NOT (nMode>2 OR bArmed) THEN
            nMiss:=nMiss+10;
        ENDIF
        bArmed:=FALSE;
        IF nMode>0 AND NOT (nMode>2 OR bArmed) THEN
            nGroup:=nGroup+1;
        ENDIF
        IF NOT RobOS() THEN
            nMiss:=nMiss+100;
        ENDIF
        IF RobOS() OR bArmed THEN
            nHits:=nHits+100;
        ENDIF
        WHILE NOT Ready() DO
            nLoops:=nLoops+1;
            nMode:=nMode-1;
        ENDWHILE
        WaitUntil Ready();
    ENDPROC

    PROC CondIo()
        IF giCode=0 AND DInput(diReady)=0 THEN
            nIo:=nIo+1;
        ENDIF
    ENDPROC

    FUNC bool Ready()
        IF nMode=0 OR RobOS()=FALSE THEN
            RETURN TRUE;
        ELSE
            RETURN FALSE;
        ENDIF
    ENDFUNC

    FUNC bool Blocked()
        IF nMode=2 THEN
            RETURN TRUE;
        ENDIF
        RETURN FALSE;
    ENDFUNC

    FUNC bool Armed()
        RETURN Ready() AND bArmed;
    ENDFUNC
ENDMODULE
