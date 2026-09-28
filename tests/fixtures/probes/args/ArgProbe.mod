MODULE ArgProbe
    ! CrossArm - argument probe: see tools/make_arg_probe.py.
    VAR num nSum:=0;
    VAR num nCount:=0;
    VAR num nFlags:=0;
    VAR num nOn:=0;
    VAR num nLast:=0;
    VAR num nAngle:=0;
    VAR num nWaits:=0;

    PROC ArgProbe()
        nSum:=0;
        nCount:=0;
        nFlags:=0;
        nOn:=0;
        nLast:=0;
        nAngle:=0;
        nWaits:=0;
        ArgRecord 3,-2.5,TRUE\Check;
        ArgRecord 4,0.5,FALSE;
        ArgRecord 2,10,TRUE\Check;
        ArgOuter 1\Check;
        ArgTurn 400;
        ArgTurn 90;
        ArgWait 0.2;
    ENDPROC

    PROC ArgRecord(num a,num b,bool on\switch Check)
        nLast:=a;
        nSum:=nSum+b;
        IF on nOn:=nOn+1;
        IF Present(Check) nFlags:=nFlags+1;
        FOR i FROM 1 TO a DO
            nCount:=nCount+1;
        ENDFOR
    ENDPROC

    PROC ArgOuter(num x\switch Check)
        ArgRecord x,1,TRUE\Check?Check;
    ENDPROC

    PROC ArgTurn(num angle)
        IF angle>360 angle:=0;
        nAngle:=nAngle+angle;
    ENDPROC

    PROC ArgWait(num t)
        WaitTime t;
        nWaits:=nWaits+1;
    ENDPROC
ENDMODULE
