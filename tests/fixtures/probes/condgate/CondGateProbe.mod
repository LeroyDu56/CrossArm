MODULE CondGateProbe
    ! CrossArm - condition-gate probe: see tools/make_condition_gate_probe.py.
    VAR num nBefore:=0;
    VAR num nThen:=0;
    VAR num nElse:=0;
    VAR num nElseIf:=0;
    VAR num nLoops:=0;
    VAR num nCase:=0;
    VAR num nAfter:=0;
    VAR string sMode:="A";

    PROC CondGateProbe()
        nBefore:=1;
        sMode:="A";
        IF OpMode()=OP_AUTO THEN
            nThen:=nThen+1;
        ELSE
            nElse:=nElse+1;
        ENDIF
        IF nBefore>5 THEN
            nThen:=nThen+10;
        ELSEIF OpMode()=OP_AUTO THEN
            nElseIf:=nElseIf+1;
        ELSE
            nElse:=nElse+10;
        ENDIF
        IF sMode="B" THEN
            nThen:=nThen+100;
        ELSEIF OpMode()=OP_AUTO THEN
            nElseIf:=nElseIf+10;
        ELSE
            nElse:=nElse+100;
        ENDIF
        WHILE OpMode()<>OP_AUTO DO
            nLoops:=nLoops+1;
        ENDWHILE
        TEST StrLen(sMode)
        CASE 1:
            nCase:=1;
        DEFAULT:
            nCase:=2;
        ENDTEST
        nAfter:=1;
    ENDPROC
ENDMODULE
