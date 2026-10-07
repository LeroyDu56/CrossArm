MODULE ExtProbe
    ! CrossArm - provided programs probe: see tools/make_external_probe.py.
    VAR num nSum:=0;
    VAR num nFlag:=0;
    VAR num nLen:=0;
    VAR num nLogged:=0;
    VAR num nBack:=0;
    VAR num nAfter:=0;
    VAR iodev log;

    PROC ExtProbe()
        nSum:=0;
        nFlag:=0;
        nLen:=0;
        nLogged:=0;
        nBack:=7;
        nAfter:=0;
        ProbeAdd 3,-2.5,TRUE;
        ProbeLog "HELLO",nBack;
        ProbeTwice nBack;
        nAfter:=nAfter+1;
    ENDPROC

    PROC ProbeLog(string text,num n)
        Open "HOME:/crossarm_probe.txt",log\Append;
        Write log,text\Num:=n;
        Close log;
    ENDPROC

    PROC ProbeTwice(INOUT num value)
        Open "HOME:/crossarm_probe.txt",log\Append;
        Write log,"twice"\Num:=value;
        Close log;
        value:=value*2;
    ENDPROC
ENDMODULE
